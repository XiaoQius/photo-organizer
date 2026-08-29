from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import IMAGE_EXTENSIONS
from app.database import get_db
from app.models.media import MediaFile
from app.schemas.media import CleanupIn, ConvertIn, MediaListOut, MediaOut
from app.services import convert, jobs
from app.services.classify import compute_quality
from app.services.thumbnail import get_thumbnail

router = APIRouter()


def _apply_filters(query, media_type: str, year, month, category, quality, tag, search):
    if media_type in {"photo", "video", "doc", "audio", "archive"}:
        query = query.filter(MediaFile.media_type == media_type)
    if category in {"normal", "screenshot", "chat_export"}:
        query = query.filter(MediaFile.category == category)
    if quality == "flagged":
        query = query.filter(MediaFile.quality_flag.isnot(None))
    elif quality in {"blurry", "dark", "bright"}:
        query = query.filter(MediaFile.quality_flag == quality)
    if tag:
        query = query.filter(MediaFile.tags.like(f'%"{tag}"%'))
    if year:
        query = query.filter(MediaFile.taken_at >= f"{year}-01-01",
                             MediaFile.taken_at < f"{year + 1}-01-01")
    if month and year:
        # 前端保证按月筛选时同时选择年份
        if month == 12:
            query = query.filter(MediaFile.taken_at < f"{year + 1}-01-01")
        else:
            query = query.filter(MediaFile.taken_at >= f"{year}-{month:02d}-01",
                                 MediaFile.taken_at < f"{year}-{month + 1:02d}-01")
    if search:
        query = query.filter(MediaFile.filename.contains(search))
    return query


ORDER_CLAUSES = {
    "time_desc": (desc(MediaFile.taken_at).nullslast(), desc(MediaFile.mtime)),
    "time_asc": (MediaFile.taken_at.asc().nullsfirst(), MediaFile.mtime.asc()),
    "size_desc": (desc(MediaFile.size), desc(MediaFile.mtime)),
    "name": (MediaFile.filename.asc(),),
}


@router.get("", response_model=MediaListOut)
def list_media(page: int = 1, page_size: int = 60, media_type: str = "",
               year: int | None = None, month: int | None = None,
               category: str = "", quality: str = "", tag: str = "",
               search: str = "", dir: str = "", on_this_day: int = 0,
               order: str = "time_desc",
               db: Session = Depends(get_db)):
    page_size = min(page_size, 500)  # 上限保护
    query = db.query(MediaFile).filter(MediaFile.status == "active")
    if on_this_day:
        # 那年今天：匹配月-日、忽略年份
        from sqlalchemy import func
        today = datetime.now().strftime("%m-%d")
        query = query.filter(func.strftime("%m-%d", MediaFile.taken_at) == today)
    if dir:
        # startswith 自动转义路径中的 %/_ 等 LIKE 通配符；选中父目录时包含全部子目录
        prefix = dir.rstrip("\\/") + "\\"
        query = query.filter(MediaFile.path.startswith(prefix))
    query = _apply_filters(query, media_type, year, month, category, quality, tag, search)
    total = query.count()
    order_by = ORDER_CLAUSES.get(order, ORDER_CLAUSES["time_desc"])
    items = (query.order_by(*order_by)
             .offset((page - 1) * page_size).limit(page_size).all())
    return MediaListOut(total=total, page=page, page_size=page_size, items=items)


@router.get("/dirs")
def list_dirs(db: Session = Depends(get_db)):
    """返回所有源目录（含各级父目录，计数为该目录下文件总数，含子目录）。"""
    counter: dict[str, int] = {}
    for (p,) in db.query(MediaFile.path).filter(MediaFile.status == "active").all():
        d = Path(p).parent
        while True:
            key = str(d)
            counter[key] = counter.get(key, 0) + 1
            parent = d.parent
            if parent == d:
                break
            d = parent
    return {"dirs": [{"dir": k, "count": v} for k, v in sorted(counter.items())]}


@router.get("/years")
def list_years(db: Session = Depends(get_db)):
    files = db.query(MediaFile.taken_at).filter(MediaFile.status == "active").all()
    years = sorted({t[0].year for t in files if t[0]}, reverse=True)
    return {"years": years}


class FixTimeIn(BaseModel):
    ids: list[int]
    mode: str                       # shift / set
    delta_hours: float = 0          # 平移小时数，可为负
    set_datetime: str | None = None  # YYYY-MM-DD HH:MM:SS


@router.post("/fix-time")
def fix_time(payload: FixTimeIn, db: Session = Depends(get_db)):
    """批量修复拍摄时间：整体平移或设为指定时间（JPEG 无损写回 EXIF）。"""
    from app.services.time_fix import fix_time as _fix
    if not payload.ids:
        raise HTTPException(status_code=400, detail="未选择文件")
    if len(payload.ids) > 100:
        job_id = jobs.start_job("fix_time", lambda job: _fix_time_worker(job, payload),
                                label=f"{len(payload.ids)} 个文件")
        return {"job_id": job_id, "total": len(payload.ids)}
    try:
        return _fix(db, payload.ids, payload.mode, payload.delta_hours, payload.set_datetime)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _fix_time_worker(job: dict, payload: FixTimeIn) -> dict:
    from app.database import SessionLocal
    from app.services.time_fix import fix_time as _fix
    job["total"] = len(payload.ids)
    db = SessionLocal()
    try:
        result = _fix(db, payload.ids, payload.mode, payload.delta_hours, payload.set_datetime)
        job["processed"] = result["updated"]
        return result
    finally:
        db.close()


@router.post("/purge-missing")
def purge_missing(db: Session = Depends(get_db)):
    """删除状态为 missing（文件已不在磁盘）的数据库记录。"""
    count = db.query(MediaFile).filter(MediaFile.status == "missing").delete()
    db.commit()
    return {"removed": count}


@router.get("/env")
def media_env():
    """运行环境检测：ffmpeg（视频封面/相似检测）与 HEIC 支持。"""
    import shutil as _shutil
    from app.services.time_extractor import HEIF_AVAILABLE
    return {"ffmpeg": bool(_shutil.which("ffmpeg")), "heif": HEIF_AVAILABLE}


@router.post("/{media_id}/open")
def media_open(media_id: int, db: Session = Depends(get_db)):
    """用系统默认播放器/看图器打开原文件（本地服务专有能力）。"""
    import os
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not Path(m.path).exists():
        raise HTTPException(status_code=404, detail="原文件已不在磁盘上")
    os.startfile(m.path)  # noqa: S606
    return {"message": "已调用系统播放器"}


@router.get("/heic")
def list_heic(db: Session = Depends(get_db)):
    files = (db.query(MediaFile)
             .filter(MediaFile.status == "active",
                     MediaFile.ext.in_({".heic", ".heif"})).all())
    return {"count": len(files), "items": [MediaOut.model_validate(m).model_dump() for m in files]}


@router.post("/analyze")
def start_quality_analyze(db: Session = Depends(get_db)):
    """后台为缺少质检结果的照片补算清晰度/曝光标记。"""
    pending = (db.query(MediaFile)
               .filter(MediaFile.status == "active", MediaFile.media_type == "photo",
                       MediaFile.blur_score.is_(None)).count())
    if pending == 0:
        return {"job_id": "", "pending": 0}
    job_id = jobs.start_job("quality", _quality_worker, label=f"{pending} 张待分析")
    return {"job_id": job_id, "pending": pending}


def _quality_worker(job: dict) -> dict:
    from app.database import SessionLocal
    from app.services.geo import nearest_city
    from app.services.time_extractor import extract_gps
    db = SessionLocal()
    flagged = 0
    try:
        files = (db.query(MediaFile)
                 .filter(MediaFile.status == "active", MediaFile.media_type == "photo",
                         MediaFile.blur_score.is_(None)).all())
        job["total"] = len(files)
        for m in files:
            if job["status"] == "cancelled":
                break
            job["current"] = m.path
            m.blur_score, m.quality_flag = compute_quality(m.path)
            if m.quality_flag:
                flagged += 1
            # 顺带补齐城市信息
            if m.city is None and m.ext.lower() in IMAGE_EXTENSIONS:
                gps = extract_gps(m.path)
                if gps:
                    m.gps_lat, m.gps_lon = gps
                    m.city = nearest_city(gps[0], gps[1])
            job["processed"] += 1
            if job["processed"] % 20 == 0:
                db.commit()
        db.commit()
        return {"flagged": flagged}
    finally:
        db.close()


ASYNC_CLEANUP_THRESHOLD = 200


@router.post("/cleanup")
def cleanup_media(payload: CleanupIn, db: Session = Depends(get_db)):
    """批量清理：trash 送系统回收站（需确认）或 move 移入指定文件夹。
    数量超过阈值时转后台任务，返回 job_id 由前端轮询进度。"""
    if payload.action not in {"trash", "move"}:
        raise HTTPException(status_code=400, detail="action 只支持 trash 或 move")
    if payload.action == "trash" and not payload.confirm_trash:
        raise HTTPException(status_code=400, detail="移入回收站需显式确认（confirm_trash=true）")
    if not payload.ids:
        raise HTTPException(status_code=400, detail="未选择文件")
    if len(payload.ids) > ASYNC_CLEANUP_THRESHOLD:
        job_id = jobs.start_job("cleanup", lambda job: _cleanup_worker(job, payload),
                                label=f"{len(payload.ids)} 个文件")
        return {"job_id": job_id, "total": len(payload.ids)}
    return _do_cleanup(db, payload)


def _do_cleanup(db: Session, payload: CleanupIn, progress: dict | None = None) -> dict:
    from send2trash import send2trash
    import shutil
    import uuid as _uuid
    from app.models.organize_log import OrganizeLog
    batch_id = _uuid.uuid4().hex[:12]
    done = failed = 0
    errors: list[str] = []
    for fid in payload.ids:
        if progress is not None and progress.get("status") == "cancelled":
            break
        m = db.get(MediaFile, fid)
        if not m or m.status != "active":
            continue
        log = OrganizeLog(batch_id=batch_id, media_file_id=fid, src_path=m.path,
                          dst_path="", action="trash" if payload.action == "trash" else "move_duplicate")
        try:
            if payload.action == "trash":
                send2trash(m.path)
                log.dst_path = "回收站"
            else:
                dst_dir = Path(payload.target_dir) if payload.target_dir else Path(m.path).parent / "待清理"
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst_path = dst_dir / m.filename
                seq = 0
                while dst_path.exists():
                    seq += 1
                    dst_path = dst_dir / f"{Path(m.filename).stem}_{seq}{Path(m.filename).suffix}"
                shutil.move(m.path, dst_path)
                log.dst_path = str(dst_path)
            m.status = "missing"
            log.status = "done"
            done += 1
        except Exception as e:  # noqa: BLE001
            log.status = "failed"
            log.message = str(e)[:500]
            errors.append(f"{m.filename}: {e}")
            failed += 1
        db.add(log)
        if progress is not None:
            progress["processed"] = progress.get("processed", 0) + 1
            if progress["processed"] % 50 == 0:
                db.commit()
    db.commit()
    return {"batch_id": batch_id, "done": done, "failed": failed, "errors": errors}


def _cleanup_worker(job: dict, payload: CleanupIn) -> dict:
    from app.database import SessionLocal
    job["total"] = len(payload.ids)
    db = SessionLocal()
    try:
        return _do_cleanup(db, payload, progress=job)
    finally:
        db.close()


@router.post("/convert")
def convert_heic(payload: ConvertIn):
    try:
        job_id = convert.start_convert(payload.media_ids, payload.quality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"job_id": job_id}


@router.get("/{media_id}/thumbnail")
def media_thumbnail(media_id: int, db: Session = Depends(get_db)):
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(status_code=404, detail="文件不存在")
    thumb = get_thumbnail(m.path, m.media_type, m.mtime)
    if not thumb:
        raise HTTPException(status_code=404, detail="无法生成缩略图")
    return FileResponse(thumb, media_type="image/jpeg")


@router.get("/{media_id}/file")
def media_file(media_id: int, db: Session = Depends(get_db)):
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = Path(m.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="原文件已不在磁盘上，请重新扫描")
    return FileResponse(path)


@router.get("/{media_id}", response_model=MediaOut)
def media_detail(media_id: int, db: Session = Depends(get_db)):
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(status_code=404, detail="文件不存在")
    return m

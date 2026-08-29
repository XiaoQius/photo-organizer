"""重复文件检测与处理：精确重复 + 相似图片/视频分组，处理支持回收站。"""

import shutil
import uuid
from pathlib import Path

from send2trash import send2trash
from sqlalchemy.orm import Session

from app.models.media import MediaFile
from app.models.organize_log import OrganizeLog
from app.services.similar import group_similar_images, group_similar_videos


def recommend_keep(files: list[MediaFile]) -> int:
    """组内推荐保留：照片按像素数（跨分辨率取最高清），无尺寸信息时按文件大小；视频按大小。"""

    def score(m: MediaFile) -> tuple:
        pixels = (m.width or 0) * (m.height or 0)
        return (pixels, m.size, m.id)

    return max(files, key=score).id


def find_duplicate_groups(db: Session) -> dict:
    """返回 {"exact": [[file...]], "similar": [[file...]]}，推荐保留项由 API 层计算。"""
    files = db.query(MediaFile).filter(MediaFile.status == "active").all()
    by_md5: dict[str, list[MediaFile]] = {}
    for m in files:
        if m.md5:
            by_md5.setdefault(m.md5, []).append(m)
    exact_groups = [sorted(g, key=lambda x: x.path) for g in by_md5.values() if len(g) > 1]

    # 已在完全重复组的只保留一个代表，避免重复报告
    consumed: set[int] = set()
    for g in exact_groups:
        consumed.update(m.id for m in g[1:])
    remaining = [m for m in files if m.id not in consumed and m.phash]
    photos = group_similar_images([m for m in remaining if m.media_type == "photo"])
    videos = group_similar_videos([m for m in remaining if m.media_type == "video"])

    return {"exact": exact_groups, "similar": photos + videos}


def resolve_duplicates(db: Session, keep_ids: list[int], remove_ids: list[int],
                       action: str, duplicates_dir: str = "") -> dict:
    """处理重复文件：action 为 trash（送回收站，显式确认）或 move（移入重复文件夹）。"""
    batch_id = uuid.uuid4().hex[:12]
    done = failed = 0
    errors: list[str] = []
    for fid in remove_ids:
        if fid in keep_ids:
            continue
        m = db.get(MediaFile, fid)
        if not m or m.status != "active":
            continue
        dst = ""
        log = OrganizeLog(batch_id=batch_id, media_file_id=fid, src_path=m.path,
                          dst_path="", action=action)
        try:
            if action == "trash":
                send2trash(m.path)
                dst = "回收站"
            else:
                dup_dir = Path(duplicates_dir) if duplicates_dir else Path(m.path).parent / "重复文件"
                dup_dir.mkdir(parents=True, exist_ok=True)
                dst_path = dup_dir / m.filename
                seq = 0
                while dst_path.exists():
                    seq += 1
                    dst_path = dup_dir / f"{Path(m.filename).stem}_{seq}{Path(m.filename).suffix}"
                shutil.move(m.path, dst_path)
                dst = str(dst_path)
            m.status = "missing"
            log.dst_path = dst
            log.status = "done"
            done += 1
        except Exception as e:  # noqa: BLE001
            log.status = "failed"
            log.message = str(e)[:500]
            errors.append(f"{m.filename}: {e}")
            failed += 1
        db.add(log)
    db.commit()
    return {"batch_id": batch_id, "done": done, "failed": failed, "errors": errors}

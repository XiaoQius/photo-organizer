"""拍摄时间批量修复：整体平移或设为指定时间。

JPEG 无损重写 EXIF（piexif，不重新压缩、不损画质）；
其他格式仅更新数据库（PNG 等容器的 EXIF 写入缺乏统一标准）。
"""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.media import MediaFile

JPEG_EXTS = {".jpg", ".jpeg"}


def _write_jpeg_exif(path: str, new_taken: datetime) -> bool:
    """无损写入 EXIF DateTimeOriginal / DateTime，失败返回 False。"""
    try:
        import piexif
        dt_str = new_taken.strftime("%Y:%m:%d %H:%M:%S").encode()
        try:
            exif_dict = piexif.load(path)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None, "Interop": {}}
        exif_dict.setdefault("0th", {})
        exif_dict.setdefault("Exif", {})
        exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str
        piexif.insert(piexif.dump(exif_dict), path)
        return True
    except Exception:
        return False


def fix_time(db: Session, ids: list[int], mode: str,
             delta_hours: float = 0, set_datetime: str | None = None) -> dict:
    """批量修复拍摄时间。mode: shift（平移）/ set（设为指定时间）。"""
    if mode not in {"shift", "set"}:
        raise ValueError("mode 只支持 shift 或 set")
    if mode == "set":
        if not set_datetime:
            raise ValueError("请提供 set_datetime（格式 YYYY-MM-DD HH:MM:SS）")
        try:
            fixed = datetime.strptime(set_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError("set_datetime 格式应为 YYYY-MM-DD HH:MM:SS")
    delta = timedelta(hours=delta_hours)

    files = db.query(MediaFile).filter(MediaFile.id.in_(ids), MediaFile.status == "active").all()
    updated = exif_written = skipped = 0
    errors: list[str] = []
    for m in files:
        base = m.taken_at or datetime.fromtimestamp(m.mtime)
        new_taken = fixed if mode == "set" else base + delta
        if m.media_type == "photo" and m.ext.lower() in JPEG_EXTS:
            if _write_jpeg_exif(m.path, new_taken):
                # EXIF 已变，文件字节更新，同步缓存键
                from app.services.thumbnail import get_thumbnail
                stat = Path(m.path).stat()
                m.mtime = stat.st_mtime
                exif_written += 1
            else:
                skipped += 1
                errors.append(f"{m.filename}: EXIF 写入失败，仅更新数据库")
        else:
            skipped += 1
        m.taken_at = new_taken
        m.taken_source = "manual"
        updated += 1
    db.commit()
    return {"updated": updated, "exif_written": exif_written, "skipped": skipped, "errors": errors}

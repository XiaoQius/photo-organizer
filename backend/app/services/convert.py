"""HEIC/HEIF → JPG 批量转换（需要 pillow-heif），转换后的文件直接入库。"""

from pathlib import Path

from app.database import SessionLocal
from app.models.media import MediaFile
from app.services import jobs
from app.services.time_extractor import HEIF_AVAILABLE
from app.services.scanner import _collect_info


def heif_available() -> bool:
    return HEIF_AVAILABLE


def start_convert(media_ids: list[int], quality: int = 90) -> str:
    if not HEIF_AVAILABLE:
        raise ValueError("未安装 pillow-heif，无法转换 HEIC，请先执行 pip install pillow-heif")
    return jobs.start_job("convert", lambda job: _convert_worker(job, media_ids, quality),
                          label=f"{len(media_ids)} 个文件")


def _convert_worker(job: dict, media_ids: list[int], quality: int) -> dict:
    db = SessionLocal()
    converted = skipped = 0
    try:
        files = (db.query(MediaFile)
                 .filter(MediaFile.id.in_(media_ids), MediaFile.status == "active")
                 .all())
        job["total"] = len(files)
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            from PIL import Image
        except ImportError:
            raise ValueError("未安装 pillow-heif，无法转换")

        for m in files:
            if job["status"] == "cancelled":
                break
            job["current"] = m.path
            if m.ext not in {".heic", ".heif"}:
                skipped += 1
                job["processed"] += 1
                continue
            dest = Path(m.path).with_suffix(".jpg")
            seq = 0
            while dest.exists():
                seq += 1
                dest = Path(m.path).with_name(f"{Path(m.path).stem}_{seq}.jpg")
            try:
                with Image.open(m.path) as img:
                    img.convert("RGB").save(dest, "JPEG", quality=quality)
                info = _collect_info(str(dest), "photo", dest.stat().st_mtime)
                db.add(MediaFile(path=str(dest), filename=dest.name, ext=".jpg",
                                 media_type="photo", size=dest.stat().st_size,
                                 mtime=dest.stat().st_mtime, **info))
                converted += 1
            except Exception as e:  # noqa: BLE001
                job["error"] = f"{m.filename}: {e}" if not job["error"] else job["error"]
            job["processed"] += 1
            db.commit()
        return {"converted": converted, "skipped": skipped}
    finally:
        db.close()

"""扫描服务：基于通用任务框架运行，提供可复用的目录扫描核心函数。"""

import os
import threading
from pathlib import Path

from app.database import SessionLocal
from app.models.media import MediaFile
from app.services import jobs
from app.services.classify import compute_quality, detect_category
from app.services.geo import nearest_city
from app.services.hashing import dhash_of_image, md5_of_file
from app.services.time_extractor import extract_gps, extract_time
from app.services.video_hash import detect_codec, video_signature


_scan_lock = threading.Lock()  # 扫描串行执行，避免并发互相干扰


def start_scan(source_dir: str) -> str:
    return jobs.start_job("scan", lambda job: _scan_worker(job, source_dir), label=source_dir)


def get_job(job_id: str) -> dict | None:
    return jobs.get_job(job_id)


def get_latest_job() -> dict | None:
    return jobs.latest_job("scan")


def cancel_scan(job_id: str) -> bool:
    return jobs.cancel_job(job_id)


def _scan_worker(job: dict, source_dir: str) -> dict:
    """任务包装：把进度写进 job 的兼容字段（current_file/added 等，供仪表盘轮询）。"""
    with _scan_lock:
        summary = scan_directory(source_dir, progress=job)
    job["added"] = summary.get("added", 0)
    job["updated"] = summary.get("updated", 0)
    job["skipped"] = summary.get("skipped", 0)
    return summary


def _type_map() -> dict[str, str]:
    """根据扫描开关设置构建 扩展名 → 文件类型 映射（照片视频始终包含）。"""
    from app.config import (
        ARCHIVE_EXTENSIONS, AUDIO_EXTENSIONS, DOC_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    )
    from app.services.settings_store import get_settings
    mapping = {}
    for ext in IMAGE_EXTENSIONS:
        mapping[ext] = "photo"
    for ext in VIDEO_EXTENSIONS:
        mapping[ext] = "video"
    db = SessionLocal()
    try:
        settings = get_settings(db)
    finally:
        db.close()
    if settings.get("scan_docs") == "1":
        for ext in DOC_EXTENSIONS:
            mapping[ext] = "doc"
    if settings.get("scan_audio") == "1":
        for ext in AUDIO_EXTENSIONS:
            mapping[ext] = "audio"
    if settings.get("scan_archives") == "1":
        for ext in ARCHIVE_EXTENSIONS:
            mapping[ext] = "archive"
    return mapping


def _split_list(value: str) -> list[str]:
    for ch in ("，", "；", ";", chr(10), chr(13)):
        value = value.replace(ch, ",")
    return [v.strip() for v in value.split(",") if v.strip()]


def _exclusions() -> tuple[set[str], list[str]]:
    """读取排除规则：返回（目录名小写集合, 归一化绝对路径前缀列表）。"""
    from app.services.settings_store import get_settings
    db = SessionLocal()
    try:
        settings = get_settings(db)
    finally:
        db.close()
    names = {n.lower() for n in _split_list(settings.get("exclude_names") or "")}
    paths = [os.path.normcase(os.path.normpath(v)) for v in _split_list(settings.get("exclude_paths") or "")]
    return names, paths


def scan_directory(source_dir: str, progress: dict | None = None) -> dict:
    """扫描目录并增量更新数据库。progress 为任务字典时可上报进度。"""
    summary = {"total": 0, "added": 0, "updated": 0, "skipped": 0, "source_dir": source_dir}
    type_map = _type_map()
    exclude_names, exclude_paths = _exclusions()

    def excluded(full_dir: str) -> bool:
        key = os.path.normcase(os.path.normpath(full_dir))
        return any(key == ep or key.startswith(ep + os.sep) for ep in exclude_paths)

    media_paths: list[tuple[str, str, float, int]] = []
    from app.config import SKIP_DIRS
    for root, dirs, files in os.walk(source_dir):
        # 剪枝：跳过系统/隐藏/依赖目录与用户配置的排除路径
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")
                   and d.lower() not in exclude_names
                   and not excluded(os.path.join(root, d))]
        for name in files:
            ext = Path(name).suffix.lower()
            media_type = type_map.get(ext)
            if not media_type:
                continue
            full = str(Path(root) / name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            media_paths.append((full, media_type, stat.st_mtime, stat.st_size))
    summary["total"] = len(media_paths)
    if progress is not None:
        progress["total"] = len(media_paths)

    db = SessionLocal()
    try:
        # 用归一化路径做键，避免不同分隔符/大小写导致重复入库
        existing = {os.path.normcase(os.path.normpath(m.path)): m for m in db.query(MediaFile).all()}
        for full, media_type, mtime, size in media_paths:
            if progress is not None and progress.get("status") == "cancelled":
                return summary
            if progress is not None:
                progress["current"] = full
                progress["current_file"] = full
            old = existing.get(os.path.normcase(os.path.normpath(full)))
            # 增量：路径已入库且大小、修改时间未变则跳过；
            # 旧数据若缺质检结果（blur_score 为空）则重新提取一次
            if old and old.mtime == mtime and old.size == size:
                needs_refresh = (media_type == "photo" and old.blur_score is None) or (media_type == "video" and old.codec is None)
                if not needs_refresh:
                    if old.status != "active":
                        old.status = "active"  # 文件在磁盘上，恢复状态
                    summary["skipped"] += 1
                    if progress is not None:
                        progress["processed"] += 1
                    continue
            info = _collect_info(full, media_type, mtime)
            if old:
                for k, v in info.items():
                    setattr(old, k, v)
                if old.status != "active":
                    old.status = "active"  # 重新扫到的文件恢复状态
                summary["updated"] += 1
            else:
                db.add(MediaFile(path=full, filename=Path(full).name, ext=Path(full).suffix.lower(),
                                 media_type=media_type, size=size, mtime=mtime, **info))
                summary["added"] += 1
            if progress is not None:
                progress["processed"] += 1
            if progress is None or progress["processed"] % 20 == 0:
                db.commit()

        # 标记本次扫描范围内已不存在的文件（不影响其他目录的记录）
        # 用与 existing 相同的归一化方式比较，避免分隔符/大小写差异导致误标
        active_keys = {os.path.normcase(os.path.normpath(p)) for p, _t, _m, _s in media_paths}
        root_norm = os.path.normcase(os.path.normpath(source_dir))
        for path, m in existing.items():
            if m.status != "active":
                continue
            if path.startswith(root_norm + os.sep) and path not in active_keys:
                m.status = "missing"
        db.commit()
    finally:
        db.close()
    return summary


def _collect_info(full: str, media_type: str, mtime: float) -> dict:
    """提取拍摄时间、GPS/城市、类别、清晰度、哈希等元数据。"""
    taken_at, taken_source = extract_time(full, media_type, mtime)
    info: dict = {
        "taken_at": taken_at,
        "taken_source": taken_source,
        "md5": md5_of_file(full),
        "width": None,
        "height": None,
        "phash": None,
        "category": "normal",
        "city": None,
        "gps_lat": None,
        "gps_lon": None,
        "blur_score": None,
        "quality_flag": None,
        "codec": None,
    }
    if media_type == "photo":
        info["category"] = detect_category(Path(full).name)
        from app.services.imaging import open_image
        with open_image(full) as img:
            if img is not None:
                info["width"], info["height"] = img.size  # 已应用 EXIF 方向
        info["phash"] = dhash_of_image(full)
        info["blur_score"], info["quality_flag"] = compute_quality(full)
        gps = extract_gps(full)
        if gps:
            info["gps_lat"], info["gps_lon"] = gps
            info["city"] = nearest_city(gps[0], gps[1])
    else:
        info["phash"] = video_signature(full) if media_type == "video" else None
        if media_type == "video":
            info["codec"] = detect_codec(full)
    return info

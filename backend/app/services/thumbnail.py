"""缩略图生成与缓存。视频封面依赖系统 ffmpeg，未安装时返回 None 降级为图标。"""

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import THUMBNAIL_DIR, THUMBNAIL_SIZE


def _cache_key(path: str, mtime: float) -> str:
    return hashlib.md5(f"{path}|{mtime}".encode()).hexdigest()


def get_thumbnail(path: str, media_type: str, mtime: float) -> Path | None:
    """返回缩略图文件路径；无法生成时返回 None。"""
    cache_file = THUMBNAIL_DIR / f"{_cache_key(path, mtime)}.jpg"
    if cache_file.exists():
        return cache_file
    try:
        if media_type == "photo":
            ok = _make_image_thumbnail(path, cache_file)
        else:
            ok = _make_video_thumbnail(path, cache_file)
    except Exception:
        ok = False
    return cache_file if ok else None


def _make_image_thumbnail(path: str, dest: Path) -> bool:
    from app.services.imaging import open_image
    with open_image(path) as img:
        if img is None:
            return False
        img = img.convert("RGB")
        img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        img.save(dest, "JPEG", quality=80)
    return True


def _make_video_thumbnail(path: str, dest: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        result = subprocess.run(
            [ffmpeg, "-y", "-ss", "1", "-i", path, "-frames:v", "1",
             "-vf", f"scale='min({THUMBNAIL_SIZE},iw)':-2", "-q:v", "5", tmp_path],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and Path(tmp_path).stat().st_size > 0:
            shutil.move(tmp_path, dest)
            return True
        Path(tmp_path).unlink(missing_ok=True)
    except Exception:
        pass
    return False

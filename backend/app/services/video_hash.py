"""视频感知指纹：ffmpeg 抽 3 帧分别算 dHash，拼成 48 位十六进制签名。"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.hashing import dhash_of_image

_FRAME_COUNT = 3


def _duration_of(path: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def video_signature(path: str) -> str | None:
    """返回 48 位十六进制签名（3 帧 × 16 位 dHash）；无 ffmpeg 或失败时返回 None。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    duration = _duration_of(path) or 0
    if duration <= 0:
        return None
    hashes: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(_FRAME_COUNT):
            ts = duration * (i + 0.5) / _FRAME_COUNT
            frame = str(Path(tmp) / f"f{i}.jpg")
            try:
                result = subprocess.run(
                    [ffmpeg, "-y", "-ss", f"{ts:.2f}", "-i", path,
                     "-frames:v", "1", "-q:v", "5", frame],
                    capture_output=True, timeout=60,
                )
            except Exception:
                return None
            h = dhash_of_image(frame) if Path(frame).exists() else None
            if not h:
                return None
            hashes.append(h)
    return "".join(hashes)


def video_distance(a: str, b: str) -> int | None:
    """两签名的逐帧汉明距离之和；长度不匹配返回 None。"""
    if len(a) != len(b) or len(a) % 16 != 0:
        return None
    total = 0
    for i in range(0, len(a), 16):
        total += bin(int(a[i:i + 16], 16) ^ int(b[i:i + 16], 16)).count("1")
    return total


def detect_codec(path: str, max_read: int = 4 * 1024 * 1024) -> str | None:
    """从文件头部采样识别视频编码（avc1=h264 / hvc1,hev1=hevc），失败返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(max_read)
    except OSError:
        return None
    if b"hvc1" in head or b"hev1" in head:
        return "hevc"
    if b"avc1" in head:
        return "h264"
    return None

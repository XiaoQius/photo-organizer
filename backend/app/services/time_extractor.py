"""拍摄时间提取：EXIF → 视频容器 → 文件名 → 修改时间，四层回退。"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

# HEIC 支持：未安装 pillow-heif 时优雅降级
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False


def extract_time(path: str, media_type: str, mtime: float) -> tuple[datetime | None, str | None]:
    """返回 (拍摄时间, 来源)，来源为 exif / video / filename / mtime。"""
    p = Path(path)
    if media_type == "photo":
        taken = _from_exif(p)
        if taken:
            return taken, "exif"
    else:
        taken = _from_video_container(p)
        if taken:
            return taken, "video"
    taken = _from_filename(p.name)
    if taken:
        return taken, "filename"
    return datetime.fromtimestamp(mtime), "mtime"


def _parse_exif_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _from_exif(path: Path) -> datetime | None:
    try:
        from PIL import Image
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            # 36867=DateTimeOriginal, 306=DateTime
            for tag in (36867, 306):
                dt = _parse_exif_datetime(exif.get(tag))
                if dt:
                    return dt
    except Exception:
        return None
    return None


def _from_video_container(path: Path) -> datetime | None:
    """解析 MP4/MOV 的 mvhd box 创建时间，纯 Python 实现。"""
    if path.suffix.lower() not in {".mp4", ".mov", ".m4v"}:
        return None
    try:
        with open(path, "rb") as f:
            creation = _find_mvhd_creation(f)
    except Exception:
        return None
    if creation is None or creation <= 0:
        return None
    try:
        base = datetime(1904, 1, 1)
        dt = base + timedelta(seconds=creation)
        if path.suffix.lower() in {".mov", ".m4v"}:
            # QuickTime 历史上存的是本地时间
            dt = dt.replace(tzinfo=timezone.utc).astimezone()
        else:
            dt = dt.replace(tzinfo=timezone.utc).astimezone()
        if dt.year < 2000 or dt.year > 2100:
            return None
        return dt.replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None


def _find_mvhd_creation(f) -> int | None:
    """在顶层 box 中递归查找 moov > mvhd，返回创建时间秒数。"""

    def walk(start: int, end: int, depth: int) -> int | None:
        pos = start
        while pos + 8 <= end:
            f.seek(pos)
            header = f.read(8)
            if len(header) < 8:
                return None
            size, box_type = int.from_bytes(header[:4], "big"), header[4:8]
            if size == 1:  # 64 位长度
                size = int.from_bytes(f.read(8), "big")
                body_start = pos + 16
            elif size == 0:  # 延伸到文件末尾
                size = end - pos
                body_start = pos + 8
            else:
                body_start = pos + 8
            if size < 8:
                return None
            if box_type == b"moov" and depth < 4:
                found = walk(body_start, pos + size, depth + 1)
                if found is not None:
                    return found
            elif box_type == b"mvhd":
                f.seek(body_start)
                data = f.read(32)
                if len(data) < 8:
                    return None
                version = data[0]
                # mvhd body: version+flags(4) 后紧跟 creation_time（v0 为 4 字节，v1 为 8 字节）
                if version == 1 and len(data) >= 12:
                    return int.from_bytes(data[4:12], "big")
                return int.from_bytes(data[4:8], "big")
            pos += size
        return None

    import os
    return walk(0, os.fstat(f.fileno()).st_size, 0)


# 文件名日期模式：IMG_20260101_123456 / 2026-01-01 12.34.56 / IMG-20260101-WA0000 等
_FILENAME_PATTERNS = [
    re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})[-_.T ](\d{2})[-_.]?(\d{2})[-_.]?(\d{2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})[_\-T ](\d{2})(\d{2})(\d{2})"),
    re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})(?=\d{6})"),
]


def _from_filename(name: str) -> datetime | None:
    for pattern in _FILENAME_PATTERNS:
        m = pattern.search(name)
        if not m:
            continue
        parts = [int(g) for g in m.groups()]
        year, month, day = parts[0], parts[1], parts[2]
        hour, minute, second = (parts + [0, 0, 0])[3:6]
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            continue
    return None


def extract_gps(path: str) -> tuple[float, float] | None:
    """从 EXIF GPS IFD 提取 (纬度, 经度)，无 GPS 时返回 None。"""
    try:
        from PIL import Image
        with Image.open(path) as img:
            exif = img.getexif()
            gps = exif.get_ifd(34853)
            if not gps:
                return None
            lat = _dms_to_degrees(gps.get(2), gps.get(1))
            lon = _dms_to_degrees(gps.get(4), gps.get(3))
            if lat is None or lon is None:
                return None
            return lat, lon
    except Exception:
        return None


def _dms_to_degrees(dms, ref) -> float | None:
    if not dms or not ref:
        return None
    try:
        # PIL 返回 IFDRational 或其序列
        values = [float(v) for v in dms]
        if len(values) != 3:
            return None
        deg = values[0] + values[1] / 60 + values[2] / 3600
        if ref in ("S", "W"):
            deg = -deg
        return deg
    except (TypeError, ValueError):
        return None

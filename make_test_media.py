# -*- coding: utf-8 -*-
"""生成测试媒体文件：EXIF 照片、重复照片、相似照片、文件名日期照片、MP4 视频。"""
import os
import shutil
import struct
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

OUT = Path(__file__).parent / "test_media"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)


def save_img(img: Image.Image, name: str, exif_dt: datetime | None):
    buf = BytesIO()
    fmt = "PNG" if name.lower().endswith(".png") else "JPEG"
    exif = Image.Exif()
    if exif_dt:
        exif[36867] = exif_dt.strftime("%Y:%m:%d %H:%M:%S")
        exif[306] = exif_dt.strftime("%Y:%m:%d %H:%M:%S")
    img.save(buf, fmt, exif=exif if exif_dt else None)
    (OUT / name).write_bytes(buf.getvalue())


base = Image.new("RGB", (800, 600), (120, 160, 200))
for x in range(0, 800, 40):
    for y in range(0, 600, 40):
        if (x + y) % 80 == 0:
            for dx in range(20):
                for dy in range(20):
                    base.putpixel((x + dx, y + dy), (250, 220, 90))

# 1. 带 EXIF 的照片
save_img(base, "vacation_001.jpg", datetime(2024, 5, 1, 10, 30, 0))
# 2. 完全重复（直接复制字节）
shutil.copy(OUT / "vacation_001.jpg", OUT / "vacation_001_copy.jpg")
# 3. 相似照片（像素轻微扰动，dHash 相近但 MD5 不同）
similar = base.copy()
for x in range(0, 800, 4):
    for y in range(3):
        similar.putpixel((x, y), (255, 255, 255))
save_img(similar, "vacation_002.jpg", datetime(2024, 5, 1, 10, 30, 5))
# 4. 无 EXIF，文件名带日期
save_img(Image.new("RGB", (600, 400), (90, 180, 120)), "IMG_20230615_080000.png", None)
# 5. 无任何时间信息 → 回退 mtime
save_img(Image.new("RGB", (400, 400), (200, 90, 90)), "unknown.png", None)


# 6. 伪 MP4：ftyp + moov>mvhd，创建时间 2023-01-10 08:00:00 (UTC)
def box(btype: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body) + 8) + btype + body


creation = int((datetime(2023, 1, 10, 8, 0, 0) - datetime(1904, 1, 1)).total_seconds())
version0_mvhd = (
    b"\x00\x00\x00\x00"                       # version + flags
    + struct.pack(">II", creation, 0)         # creation_time, modification_time
    + struct.pack(">II", 600, 600 * 10)       # timescale, duration
    + struct.pack(">I", 0x00010000)           # rate
    + struct.pack(">H", 0x0100)               # volume
    + b"\x00" * 10                            # reserved
    + b"\x00" * 36                            # matrix
    + b"\x00" * 24                            # predefined
    + struct.pack(">I", 2)                    # next_track_id
)
mp4 = box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2") + box(b"moov", box(b"mvhd", version0_mvhd))
(OUT / "clip_20230110.mp4").write_bytes(mp4)

# 调整 mtime 以测试回退
t = datetime(2022, 3, 8, 12, 0, 0).timestamp()
os.utime(OUT / "unknown.png", (t, t))

print("test media created at", OUT)
for p in sorted(OUT.iterdir()):
    print(" -", p.name, p.stat().st_size, "bytes")

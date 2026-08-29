"""文件哈希：MD5 精确重复判定 + 图片 dHash 感知哈希。"""

import hashlib
from pathlib import Path


def md5_of_file(path: str) -> str | None:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def dhash_of_image(path: str) -> str | None:
    """dHash：缩放到 9x8 灰度后比较相邻像素，得到 64 位十六进制哈希。"""
    from app.services.imaging import open_image
    with open_image(path) as img:
        if img is None:
            return None
        img = img.convert("L").resize((9, 8))
        pixels = list(img.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if pixels[row * 9 + col] > pixels[row * 9 + col + 1] else 0)
    return f"{bits:016x}"


def hamming_distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")

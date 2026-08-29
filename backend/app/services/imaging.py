"""图片读取统一入口：自动应用 EXIF 方向（手机竖拍照片常用），避免缩略图/质检/哈希方向错误。"""

from contextlib import contextmanager


@contextmanager
def open_image(path: str):
    """打开图片并应用 EXIF 方向矫正；失败时 yield None。调用方负责判空。"""
    try:
        from PIL import Image, ImageOps
        img = Image.open(path)
    except Exception:
        yield None
        return
    try:
        img.load()
        transposed = ImageOps.exif_transpose(img)
        yield transposed
    except Exception:
        yield None
    finally:
        img.close()

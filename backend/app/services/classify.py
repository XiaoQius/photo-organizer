"""文件类别识别与废片质检（模糊/过暗/过曝），纯 Pillow 实现无新依赖。"""

import re

# 截图类：Screenshot_20240101_120000 / 屏幕截图 / 截屏 / MiuiScreenshot 等
_SCREENSHOT_PATTERNS = [
    re.compile(r"^screenshot", re.IGNORECASE),
    re.compile(r"^screen[_-]?shot", re.IGNORECASE),
    re.compile(r"^screencapture", re.IGNORECASE),
    re.compile(r"^screen[_-]?capture", re.IGNORECASE),
    re.compile(r"^miui[-_]?screenshot", re.IGNORECASE),
    re.compile(r"[截屏屏幕截图]"),
    re.compile(r"^photoeditor", re.IGNORECASE),
]

# 聊天/社交导出类：微信图片_ / mmexport / wx_camera / IMG-20260101-WA0000 等
_CHAT_EXPORT_PATTERNS = [
    re.compile(r"^mmexport", re.IGNORECASE),
    re.compile(r"^微信图片"),
    re.compile(r"^wx_camera", re.IGNORECASE),
    re.compile(r"^wximage", re.IGNORECASE),
    re.compile(r"^weixin", re.IGNORECASE),
    re.compile(r"^img[-_]\d{8}[-_]wa\d{4}", re.IGNORECASE),
    re.compile(r"^save\d{14}", re.IGNORECASE),
]


def detect_category(filename: str) -> str:
    """根据文件名识别类别：normal / screenshot / chat_export。"""
    for p in _SCREENSHOT_PATTERNS:
        if p.search(filename):
            return "screenshot"
    for p in _CHAT_EXPORT_PATTERNS:
        if p.search(filename):
            return "chat_export"
    return "normal"


CATEGORY_LABELS = {"normal": "照片", "screenshot": "截图", "chat_export": "聊天导出"}


def compute_quality(path: str) -> tuple[float | None, str | None]:
    """返回 (清晰度得分, 质检标记)。标记：blurry / dark / bright / None。"""
    from app.services.imaging import open_image
    with open_image(path) as img:
        if img is None:
            return None, None
        img = img.convert("L")
        img.thumbnail((256, 256))
        pixels = list(img.getdata())
        w, h = img.size
    if w < 3 or h < 3:
        return None, None
    mean = sum(pixels) / len(pixels)

    # 拉普拉斯核 [0,1,0;1,-4,1;0,1,0] 的响应方差
    responses = []
    for y in range(1, h - 1):
        top = (y - 1) * w
        mid = y * w
        bot = (y + 1) * w
        for x in range(1, w - 1):
            lap = (pixels[top + x] + pixels[bot + x] + pixels[mid + x - 1]
                   + pixels[mid + x + 1] - 4 * pixels[mid + x])
            responses.append(lap)
    if not responses:
        return None, None
    n = len(responses)
    m = sum(responses) / n
    variance = sum((r - m) ** 2 for r in responses) / n

    from app.config import BLUR_THRESHOLD, BRIGHT_THRESHOLD, DARK_THRESHOLD
    flag = None
    if variance < BLUR_THRESHOLD:
        flag = "blurry"
    elif mean < DARK_THRESHOLD:
        flag = "dark"
    elif mean > BRIGHT_THRESHOLD:
        flag = "bright"
    return round(variance, 1), flag

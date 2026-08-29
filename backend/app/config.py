import sys
from pathlib import Path

# 开发模式：数据放在 backend/ 下；打包成 exe 后：放在 exe 旁的 data/ 目录
APP_DIR = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent / "data"
else:
    BASE_DIR = APP_DIR
BASE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{BASE_DIR / 'photo_organizer.db'}"

# 缩略图缓存目录
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
THUMBNAIL_DIR.mkdir(exist_ok=True)

# 缩略图最长边（像素）
THUMBNAIL_SIZE = 400

# 支持的媒体扩展名（小写）
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tiff", ".tif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".3gp", ".mpg", ".mpeg"}

# 其他类型文件扩展名（按扫描开关启用）
DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".md", ".csv", ".epub", ".mobi",
}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".ape"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".iso"}

# 媒体类型 → 中文标签（{type} 目录变量、界面显示）
TYPE_LABELS = {
    "photo": "照片",
    "video": "视频",
    "doc": "文档",
    "audio": "音频",
    "archive": "压缩包",
}
# 统一重命名时的文件名前缀
TYPE_PREFIXES = {"photo": "IMG", "video": "VID", "doc": "DOC", "audio": "AUD", "archive": "ARC"}

# 扫描时跳过的目录名（系统/垃圾/版本库目录，避免无效遍历）
SKIP_DIRS = {
    "$RECYCLE.BIN", "System Volume Information", "$RECYCLE.BIN",
    "node_modules", ".git", ".svn", "__pycache__", ".venv", "venv",
    ".thumbnails", ".Trash-1000", "lost+found", "$WINDOWS.~BT",
}

# 感知哈希汉明距离阈值，小于该值视为相似图片
PHASH_DISTANCE_THRESHOLD = 8
# 视频三帧签名：距离阈值（每帧 8 × 3）
VIDEO_PHASH_DISTANCE_THRESHOLD = 24
# 视频相似两两比对的数量上限（图片用 BK-tree 无上限）
VIDEO_PHASH_MAX_COMPARE = 2000

# 废片检测阈值（基于最长边 256px 的灰度缩略图）
BLUR_THRESHOLD = 40        # 拉普拉斯方差低于该值视为模糊
DARK_THRESHOLD = 45        # 平均亮度低于该值视为过暗
BRIGHT_THRESHOLD = 228     # 平均亮度高于该值视为过曝

# GPS 反解城市名的最大距离（公里），超过视为未知地点
CITY_MAX_DISTANCE_KM = 120

# 文件夹监控轮询间隔（秒）
WATCH_INTERVAL_SECONDS = 60

# 默认整理设置
DEFAULT_SETTINGS = {
    "folder_structure": "Y/M",        # 兼容保留：Y/M = 年/月, Y/M/D = 年/月/日
    "naming": "standard",             # 兼容保留：standard = 统一重命名, keep = 保留原名
    "folder_template": "",            # 自定义目录模板，如 {year}/{month}/{city}，优先于 folder_structure
    "name_template": "",              # 自定义文件名模板，如 {prefix}_{datetime}，优先于 naming
    "default_mode": "move",           # move / copy
    "last_source_dir": "",
    "last_target_dir": "",
    "watch_dir": "",                  # 监控目录
    "watch_enabled": "0",             # 1 = 开启监控
    "watch_auto_organize": "0",       # 1 = 新文件自动归档
    "watch_target_dir": "",           # 自动归档目标目录
    "scan_docs": "0",                 # 1 = 扫描时包含文档
    "scan_audio": "0",                # 1 = 扫描时包含音频
    "scan_archives": "0",             # 1 = 扫描时包含压缩包
    "exclude_names": "node_modules,.git,dist,build,out,vendor,target,__pycache__,.venv,venv,.next,.nuxt,.cache,.idea,.vscode,__MACOSX,site-packages,.gradle,thumbnails",
    "exclude_paths": "",              # 每行/逗号分隔的绝对路径，整棵目录树跳过
}


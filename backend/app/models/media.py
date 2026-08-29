from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MediaFile(Base):
    """扫描入库的媒体文件"""

    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, comment="文件绝对路径")
    filename: Mapped[str] = mapped_column(String(512), comment="文件名")
    ext: Mapped[str] = mapped_column(String(16), comment="扩展名（小写，含点）")
    media_type: Mapped[str] = mapped_column(String(16), comment="类型：photo / video")
    size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小（字节）")
    mtime: Mapped[float] = mapped_column(Float, default=0, comment="文件修改时间戳")
    taken_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="拍摄时间")
    taken_source: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="拍摄时间来源：exif / video / filename / mtime")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="宽度（仅图片）")
    height: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="高度（仅图片）")
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="文件 MD5")
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="感知哈希：图片 16 位 dHash；视频 48 位三帧签名")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态：active / missing / organized")
    category: Mapped[str] = mapped_column(String(16), default="normal", comment="类别：normal / screenshot / chat_export")
    city: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="GPS 反解的城市名")
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True, comment="EXIF GPS 纬度")
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True, comment="EXIF GPS 经度")
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="清晰度得分（拉普拉斯方差）")
    quality_flag: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="质检标记：blurry / dark / bright")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="AI 场景标签")
    codec: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="视频编码：h264 / hevc 等")
    codec: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="视频编码：h264 / hevc 等")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Setting(Base):
    """键值形式的应用设置"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

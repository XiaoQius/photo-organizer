from datetime import datetime

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OrganizeLog(Base):
    """整理执行日志，一条对应一个文件的一次动作"""

    __tablename__ = "organize_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True, comment="整理批次 ID")
    media_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联媒体文件 ID")
    src_path: Mapped[str] = mapped_column(String(1024), comment="源路径")
    dst_path: Mapped[str] = mapped_column(String(1024), comment="目标路径")
    action: Mapped[str] = mapped_column(String(24), comment="动作：move / copy / skip / delete / trash / move_duplicate / undo_move / undo_copy")
    status: Mapped[str] = mapped_column(String(16), comment="结果：done / failed / skipped")
    message: Mapped[str] = mapped_column(String(512), default="", comment="备注（跳过/失败原因等）")
    undone: Mapped[int] = mapped_column(Integer, default=0, comment="该动作是否已被撤销：0/1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

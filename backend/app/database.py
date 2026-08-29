from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns():
    """轻量迁移：为已存在的表补齐新增列和索引（SQLite 只支持 ADD COLUMN）。"""
    new_columns = {
        "media_files": {
            "category": "VARCHAR(16) DEFAULT 'normal'",
            "city": "VARCHAR(64)",
            "gps_lat": "FLOAT",
            "gps_lon": "FLOAT",
            "blur_score": "FLOAT",
            "quality_flag": "VARCHAR(16)",
            "tags": "JSON",
            "codec": "VARCHAR(16)",
        },
        "organize_logs": {
            "undone": "INTEGER DEFAULT 0",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in new_columns.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        # 常用查询索引（照片墙按状态+时间排序/筛选）
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_status_taken ON media_files (status, taken_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_status_type ON media_files (status, media_type)"))

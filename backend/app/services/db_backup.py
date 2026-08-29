"""数据库备份与恢复：SQLite 在线备份到 backend/backups/，恢复前自动再备份当前库。"""

import re
import time
from pathlib import Path

from app.config import BASE_DIR
from app.database import engine, init_db

BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
_NAME_RE = re.compile(r"^photo_organizer-[\d-]+\.db$")


def list_backups() -> list[dict]:
    items = []
    for f in sorted(BACKUP_DIR.glob("photo_organizer-*.db"), reverse=True):
        items.append({"filename": f.name, "size": f.stat().st_size,
                      "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))})
    return items


def create_backup() -> dict:
    """使用 SQLite 在线备份 API，服务运行中也能安全备份。"""
    dest = BACKUP_DIR / f"photo_organizer-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src_conn = engine.raw_connection()
    try:
        dest_conn = __import__("sqlite3").connect(str(dest))
        try:
            with dest_conn:
                src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return {"filename": dest.name, "size": dest.stat().st_size}


def restore_backup(filename: str) -> dict:
    """恢复指定备份：先把当前数据库再备份一份，然后覆盖并重建连接。"""
    if not _NAME_RE.match(filename):
        raise ValueError("非法的备份文件名")
    src = BACKUP_DIR / filename
    if not src.exists():
        raise ValueError("备份文件不存在")
    safety = create_backup()
    db_file = Path(BASE_DIR / "photo_organizer.db")
    # 关闭所有连接后覆盖（Windows 上文件被占用时无法覆盖）
    engine.dispose()
    import shutil
    shutil.copy2(src, db_file)
    init_db()
    return {"restored": filename, "safety_backup": safety["filename"]}


def delete_backup(filename: str) -> None:
    if not _NAME_RE.match(filename):
        raise ValueError("非法的备份文件名")
    (BACKUP_DIR / filename).unlink(missing_ok=True)

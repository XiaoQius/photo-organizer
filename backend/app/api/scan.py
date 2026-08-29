from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.media import FsListOut, ScanStartIn
from app.services import scanner
from app.services.settings_store import update_settings

router = APIRouter()


@router.post("/start")
def start_scan(payload: ScanStartIn):
    source = Path(payload.source_dir)
    if not source.exists():
        raise HTTPException(status_code=400, detail="目录不存在，请检查路径")
    if not source.is_dir():
        raise HTTPException(status_code=400, detail="路径不是目录")
    job_id = scanner.start_scan(str(source.resolve()))
    # 记住上次扫描目录
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        update_settings(db, {"last_source_dir": str(source.resolve())})
    finally:
        db.close()
    return {"job_id": job_id}


@router.get("/status/{job_id}")
def scan_status(job_id: str):
    job = scanner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/latest")
def latest_scan():
    job = scanner.get_latest_job()
    return job or {"status": "none"}


@router.post("/cancel/{job_id}")
def cancel_scan(job_id: str):
    if not scanner.cancel_scan(job_id):
        raise HTTPException(status_code=400, detail="任务不存在或已结束")
    return {"message": "已请求取消"}


@router.get("/fs/list", response_model=FsListOut)
def list_dir(path: str = ""):
    """浏览本机目录：path 为空时返回盘符列表（Windows）。"""
    import string
    if not path:
        drives = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
        return FsListOut(path="", parent=None, directories=drives)
    target = Path(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="目录不存在")
    target = target.resolve()
    directories: list[str] = []
    try:
        for child in sorted(target.iterdir(), key=lambda c: c.name.lower()):
            if child.is_dir() and not child.name.startswith((".", "$")):
                directories.append(str(child))
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"无法读取目录：{e}")
    parent = str(target.parent) if target.parent != target else None
    return FsListOut(path=str(target), parent=parent, directories=directories)

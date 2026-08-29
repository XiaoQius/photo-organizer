from fastapi import APIRouter
from pydantic import BaseModel

from app.database import SessionLocal
from app.services import watcher
from app.services.settings_store import get_settings, update_settings

router = APIRouter()


@router.get("/status")
def watch_status():
    db = SessionLocal()
    try:
        settings = get_settings(db)
    finally:
        db.close()
    return {
        "watch_dir": settings.get("watch_dir", ""),
        "watch_target_dir": settings.get("watch_target_dir", ""),
        "watch_auto_organize": settings.get("watch_auto_organize") == "1",
        "enabled": settings.get("watch_enabled") == "1",
        **watcher.status(),
    }


class WatchToggleIn(BaseModel):
    enabled: bool
    watch_dir: str = ""
    target_dir: str = ""
    auto_organize: bool = False


@router.post("/toggle")
def watch_toggle(payload: WatchToggleIn):
    if payload.enabled and not payload.watch_dir.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="请先填写监控目录")
    db = SessionLocal()
    try:
        update_settings(db, {
            "watch_enabled": "1" if payload.enabled else "0",
            "watch_dir": payload.watch_dir.strip(),
            "watch_target_dir": payload.target_dir.strip(),
            "watch_auto_organize": "1" if payload.auto_organize else "0",
        })
    finally:
        db.close()
    watcher.restart_if_enabled()
    return {"message": "监控已开启" if payload.enabled else "监控已关闭"}


@router.post("/run-now")
def watch_run_now():
    try:
        result = watcher.run_once()
        return {"message": result}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

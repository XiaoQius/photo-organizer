"""文件夹监控：轮询 watch_dir，可选自动把新文件按当前规则归档到目标目录。"""

import threading
import time

from app.config import WATCH_INTERVAL_SECONDS
from app.database import SessionLocal
from app.services import jobs
from app.services.organizer import build_plan, execute_plan
from app.services.scanner import scan_directory
from app.services.settings_store import get_settings

_state = {
    "thread": None,
    "running": False,
    "last_run": None,
    "last_result": "",
    "error": "",
}
_lock = threading.Lock()


def status() -> dict:
    with _lock:
        return {
            "running": _state["running"],
            "last_run": _state["last_run"],
            "last_result": _state["last_result"],
            "error": _state["error"],
        }


def restart_if_enabled():
    """根据设置启动/停止监控线程（应用启动时与设置变更后调用）。"""
    db = SessionLocal()
    try:
        settings = get_settings(db)
    finally:
        db.close()
    if settings.get("watch_enabled") == "1" and settings.get("watch_dir"):
        _ensure_started()
    else:
        stop()


def _ensure_started():
    with _lock:
        if _state["running"] and _state["thread"] and _state["thread"].is_alive():
            return
        _state["running"] = True
        _state["thread"] = threading.Thread(target=_loop, daemon=True)


def stop():
    with _lock:
        _state["running"] = False


def run_once() -> str:
    """立即执行一次检查（扫描 + 可选自动归档），返回结果摘要。"""
    db = SessionLocal()
    try:
        settings = get_settings(db)
        if not settings.get("watch_dir"):
            raise ValueError("请先在设置中填写监控目录")
        summary = scan_directory(settings["watch_dir"])
        result = f"扫描：新增 {summary['added']}，更新 {summary['updated']}"
        if settings.get("watch_auto_organize") == "1" and settings.get("watch_target_dir") and summary["added"] > 0:
            # 只归档监控目录里的活动文件
            from app.models.media import MediaFile
            prefix = settings["watch_dir"].rstrip(chr(92) + "/") + chr(92)
            ids = (db.query(MediaFile.id)
                   .filter(MediaFile.status == "active",
                           MediaFile.path.like(f"{prefix}%"))
                   .scalars().all())
            if ids:
                plan_id = build_plan(db, ids, settings["watch_target_dir"], "move",
                                     settings.get("folder_structure", "Y/M"),
                                     settings.get("naming", "standard"),
                                     settings.get("folder_template", ""),
                                     settings.get("name_template", ""))
                result += "；" + str(execute_plan(db, plan_id))
        with _lock:
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_result"] = result
            _state["error"] = ""
        return result
    except Exception as e:  # noqa: BLE001
        with _lock:
            _state["error"] = str(e)
        raise
    finally:
        db.close()


def _loop():
    while True:
        with _lock:
            if not _state["running"]:
                return
        try:
            run_once()
        except Exception:  # noqa: BLE001
            pass  # 错误已记录到 _state
        for _ in range(WATCH_INTERVAL_SECONDS * 10):
            with _lock:
                if not _state["running"]:
                    return
            time.sleep(0.1)

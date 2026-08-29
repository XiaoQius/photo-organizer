"""通用后台任务框架：线程执行 + 内存任务状态，前端轮询进度。"""

import threading
import time
import uuid

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def create_job(kind: str, label: str = "") -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "kind": kind,
        "label": label,
        "status": "running",
        "total": 0,
        "processed": 0,
        "current": "",
        "result": {},
        "error": "",
        "started_at": time.time(),
        "finished_at": None,
    }
    with _lock:
        _jobs[job_id] = job
        # 每类任务只保留最近 5 个已结束的任务
        finished = [j for j in _jobs.values() if j["status"] != "running"]
        if len(finished) > 15:
            for old in sorted(finished, key=lambda j: j["started_at"])[: len(finished) - 15]:
                _jobs.pop(old["job_id"], None)
    return job


def start_job(kind: str, worker, label: str = "") -> str:
    """在线程中运行 worker(job)，返回 job_id。worker 通过 job 字典上报进度。"""
    job = create_job(kind, label)

    def _run():
        try:
            result = worker(job)
            if result:
                job["result"] = result
            if job["status"] == "running":
                job["status"] = "done"
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            job["finished_at"] = time.time()
            job["current"] = ""

    threading.Thread(target=_run, daemon=True).start()
    return job["job_id"]


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def latest_job(kind: str | None = None) -> dict | None:
    with _lock:
        candidates = [j for j in _jobs.values() if kind is None or j["kind"] == kind]
        if not candidates:
            return None
        return dict(max(candidates, key=lambda j: j["started_at"]))


def cancel_job(job_id: str) -> bool:
    with _lock:
        job = _jobs.get(job_id)
        if job and job["status"] == "running":
            job["status"] = "cancelled"
            return True
        return False

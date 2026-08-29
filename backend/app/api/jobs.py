from fastapi import APIRouter, HTTPException

from app.services import jobs

router = APIRouter()


@router.get("/{job_id}")
def job_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/latest/{kind}")
def latest_job(kind: str):
    job = jobs.latest_job(kind)
    return job or {"status": "none", "kind": kind}

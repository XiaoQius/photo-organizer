from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ai_tag, jobs

router = APIRouter()


@router.get("/config")
def ai_config():
    return {"configured": ai_tag.is_configured(), "model": ai_tag.llm_config()["model"]}


class TagStartIn(BaseModel):
    max_images: int = 200


@router.post("/tag")
def start_tagging(payload: TagStartIn):
    try:
        job_id = ai_tag.start_tagging(payload.max_images)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"job_id": job_id}


@router.get("/tag/{job_id}")
def tagging_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job

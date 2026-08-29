from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import db_backup

router = APIRouter()


@router.get("/backups")
def backups():
    return {"items": db_backup.list_backups()}


@router.post("/backup")
def backup():
    return db_backup.create_backup()


class RestoreIn(BaseModel):
    filename: str


@router.post("/restore")
def restore(payload: RestoreIn):
    try:
        return db_backup.restore_backup(payload.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/backups/delete")
def delete_backup(payload: RestoreIn):
    try:
        db_backup.delete_backup(payload.filename)
        return {"message": "已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

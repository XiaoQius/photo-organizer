from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.schemas.media import OrganizeExecuteIn, OrganizePlanIn, OrganizePlanOut, OrganizePlanUpdateIn, OrganizeUndoIn
from app.services import organizer
from app.services.settings_store import update_settings

router = APIRouter()


@router.post("/plan", response_model=OrganizePlanOut)
def create_plan(payload: OrganizePlanIn, db: Session = Depends(get_db)):
    from pathlib import Path
    if not payload.target_dir.strip():
        raise HTTPException(status_code=400, detail="请填写目标目录")
    if payload.mode not in {"move", "copy"}:
        raise HTTPException(status_code=400, detail="mode 只支持 move 或 copy")
    target = Path(payload.target_dir)
    # 目标目录不存在时自动创建
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"无法创建目标目录：{e}")
    plan_id = organizer.build_plan(db, payload.media_ids or [], payload.target_dir,
                                   payload.mode, payload.folder_structure, payload.naming,
                                   payload.folder_template, payload.name_template)
    plan = organizer.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=500, detail="计划生成失败")
    # 记住上次目标目录与规则
    from app.services.settings_store import get_settings
    sdb = SessionLocal()
    try:
        settings = get_settings(sdb)
        update_settings(sdb, {
            "last_target_dir": payload.target_dir,
            "default_mode": payload.mode,
            "folder_structure": payload.folder_structure,
            "naming": payload.naming,
            # 用户显式输入过模板才覆盖
            "folder_template": payload.folder_template.strip() or settings.get("folder_template", ""),
            "name_template": payload.name_template.strip() or settings.get("name_template", ""),
        })
    finally:
        sdb.close()
    return {"plan_id": plan_id, "items": plan["items"]}


@router.patch("/plan/{plan_id}", response_model=OrganizePlanOut)
def patch_plan(plan_id: str, payload: OrganizePlanUpdateIn):
    plan = organizer.update_plan_items(plan_id, payload.excluded_ids, payload.dst_overrides)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在或已过期，请重新生成")
    return {"plan_id": plan_id, "items": plan["items"]}


@router.get("/plan/{plan_id}", response_model=OrganizePlanOut)
def get_plan(plan_id: str):
    plan = organizer.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在或已过期，请重新生成")
    return {"plan_id": plan_id, "items": plan["items"]}


@router.post("/execute")
def execute_plan(payload: OrganizeExecuteIn, db: Session = Depends(get_db)):
    try:
        return organizer.execute_plan(db, payload.plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/undo")
def undo_batch(payload: OrganizeUndoIn, db: Session = Depends(get_db)):
    try:
        return organizer.undo_batch(db, payload.batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class CleanEmptyIn(BaseModel):
    dirs: list[str]


@router.post("/clean-empty")
def clean_empty_dirs(payload: CleanEmptyIn):
    """删除空的源目录（自底向上逐级清理，遇非空或盘根停止）。"""
    from pathlib import Path
    removed = 0
    for raw in payload.dirs:
        p = Path(raw)
        while p is not None and p != p.parent:
            try:
                next(p.iterdir())
                break  # 目录非空
            except StopIteration:
                pass
            except OSError:
                break
            try:
                p.rmdir()
                removed += 1
            except OSError:
                break
            p = p.parent
    return {"removed": removed}


@router.get("/logs")
def organize_logs(limit: int = 20, db: Session = Depends(get_db)):
    return organizer.get_logs(db, limit)


@router.get("/logs/export")
def export_logs(batch_id: str, db: Session = Depends(get_db)):
    csv_text = organizer.export_batch_csv(db, batch_id)
    filename = f"organize-{batch_id}.csv"
    return Response(
        content="﻿".encode("utf-8") + csv_text.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

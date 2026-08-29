from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.media import DuplicatesResolveIn, MediaOut
from app.services import duplicates as duplicates_service

router = APIRouter()


@router.get("")
def duplicate_groups(db: Session = Depends(get_db)):
    groups = duplicates_service.find_duplicate_groups(db)

    def to_group(idx: int, kind: str, files):
        return {
            "key": f"{kind}-{idx}",
            "kind": kind,
            "keep_id": files[0].id,
            # 智能推荐：跨分辨率/压缩版本时建议保留最高清的一张
            "recommended_id": duplicates_service.recommend_keep(files),
            "files": [MediaOut.model_validate(m).model_dump() for m in files],
        }

    return {
        "exact": [to_group(i, "exact", g) for i, g in enumerate(groups["exact"])],
        "similar": [to_group(i, "similar", g) for i, g in enumerate(groups["similar"])],
    }


@router.post("/resolve")
def resolve_duplicates(payload: DuplicatesResolveIn, db: Session = Depends(get_db)):
    if payload.action not in {"move", "trash"}:
        raise HTTPException(status_code=400, detail="action 只支持 move 或 trash")
    if payload.action == "trash" and not payload.confirm_trash:
        raise HTTPException(status_code=400, detail="移入回收站需显式确认（confirm_trash=true）")
    if not payload.remove_ids:
        raise HTTPException(status_code=400, detail="未选择要处理的文件")
    return duplicates_service.resolve_duplicates(db, payload.keep_ids,
                                                 payload.remove_ids, payload.action,
                                                 payload.duplicates_dir)

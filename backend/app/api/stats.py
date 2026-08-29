from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import stats_service

router = APIRouter()


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return stats_service.overview(db)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.settings_store import get_settings, update_settings

router = APIRouter()


class SettingsIn(BaseModel):
    folder_structure: str | None = None
    naming: str | None = None
    folder_template: str | None = None
    name_template: str | None = None
    default_mode: str | None = None
    last_source_dir: str | None = None
    last_target_dir: str | None = None
    scan_docs: str | None = None
    scan_audio: str | None = None
    scan_archives: str | None = None
    exclude_names: str | None = None
    exclude_paths: str | None = None


@router.get("")
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


@router.put("")
def save_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    return update_settings(db, payload.model_dump(exclude_unset=True))

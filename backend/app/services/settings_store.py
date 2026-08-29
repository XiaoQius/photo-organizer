"""应用设置读写：DB 键值表 + 默认值合并。"""

from sqlalchemy.orm import Session

from app.config import DEFAULT_SETTINGS
from app.models.media import Setting


def get_settings(db: Session) -> dict:
    stored = {s.key: s.value for s in db.query(Setting).all()}
    return {**DEFAULT_SETTINGS, **stored}


def update_settings(db: Session, payload: dict) -> dict:
    for key, value in payload.items():
        if key not in DEFAULT_SETTINGS:
            continue
        setting = db.get(Setting, key)
        if setting:
            setting.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
    return get_settings(db)

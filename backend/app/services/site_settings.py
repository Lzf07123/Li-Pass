from sqlalchemy.orm import Session

from app.models.site_setting import SiteSetting

PUBLIC_REGISTRATION_ENABLED_KEY = "public_registration_enabled"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def get_site_setting_bool(db: Session, key: str, default: bool) -> bool:
    row = db.get(SiteSetting, key)
    if row is None:
        return default
    return row.value.strip().lower() in _TRUE_VALUES


def set_site_setting_bool(db: Session, key: str, value: bool) -> None:
    text = "true" if value else "false"
    row = db.get(SiteSetting, key)
    if row is None:
        db.add(SiteSetting(key=key, value=text))
    else:
        row.value = text
    db.commit()


def get_site_setting_int(db: Session, key: str, default: int) -> int:
    row = db.get(SiteSetting, key)
    if row is None:
        return default
    try:
        return int(row.value.strip())
    except ValueError:
        return default


def set_site_setting_int(db: Session, key: str, value: int) -> None:
    text = str(value)
    row = db.get(SiteSetting, key)
    if row is None:
        db.add(SiteSetting(key=key, value=text))
    else:
        row.value = text
    db.commit()

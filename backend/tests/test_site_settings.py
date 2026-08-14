from app.models.site_setting import SiteSetting
from app.services.site_settings import get_site_setting_int, set_site_setting_int


def test_get_site_setting_int_returns_default_without_row(db_session) -> None:
    assert get_site_setting_int(db_session, "missing_key", 24) == 24


def test_set_and_get_site_setting_int_roundtrip(db_session) -> None:
    set_site_setting_int(db_session, "interval_hours", 48)
    assert get_site_setting_int(db_session, "interval_hours", 24) == 48

    set_site_setting_int(db_session, "interval_hours", 168)
    assert get_site_setting_int(db_session, "interval_hours", 24) == 168


def test_get_site_setting_int_falls_back_on_dirty_value(db_session) -> None:
    db_session.add(SiteSetting(key="interval_hours", value="not-a-number"))
    db_session.commit()
    assert get_site_setting_int(db_session, "interval_hours", 24) == 24

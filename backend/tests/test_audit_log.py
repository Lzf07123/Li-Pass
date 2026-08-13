import uuid

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services.audit import log_audit, log_rate_limit_rejected_once, mask_phone


def test_log_audit_writes_category(db_session) -> None:
    log_audit(
        db_session,
        "user",
        str(uuid.uuid4()),
        "login",
        category="auth",
        ip="127.0.0.1",
    )
    row = db_session.scalar(select(AuditLog))
    assert row is not None
    assert row.category == "auth"


def test_log_audit_falls_back_to_other_for_unknown_category(db_session) -> None:
    log_audit(
        db_session,
        "user",
        str(uuid.uuid4()),
        "weird_action",
        category="not-a-real-category",
    )
    row = db_session.scalar(select(AuditLog))
    assert row is not None
    assert row.category == "other"


def test_rate_limit_rejection_logged_once_per_window(db_session) -> None:
    log_rate_limit_rejected_once(db_session, "login", 31, 30, increment=1, ip="x")
    log_rate_limit_rejected_once(db_session, "login", 32, 30, increment=1, ip="x")
    rows = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "rate_limit_rejected")
    ).all()
    assert len(rows) == 1


def test_rate_limit_rejection_logged_once_for_batch_increment(db_session) -> None:
    log_rate_limit_rejected_once(
        db_session, "admin_batch_invite", 150, 100, increment=100, ip="x"
    )
    log_rate_limit_rejected_once(
        db_session, "admin_batch_invite", 250, 100, increment=100, ip="x"
    )
    rows = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "rate_limit_rejected")
    ).all()
    assert len(rows) == 1


def test_mask_phone_hides_middle_digits() -> None:
    assert mask_phone("+8613800000000") == "+86****0000"

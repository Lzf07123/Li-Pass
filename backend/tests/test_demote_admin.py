import pytest

from app.models.user import User, UserRole
from scripts.demote_admin import main as demote_main


def _make_user(db_session, email: str, role: UserRole) -> User:
    user = User(
        email=email,
        password_hash="unused",
        nickname=email.split("@")[0],
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_demote_admin_sets_role_to_user(db_session) -> None:
    _make_user(db_session, "keeper@example.com", UserRole.admin)
    user = _make_user(db_session, "admin@example.com", UserRole.admin)

    demote_main("admin@example.com", db=db_session)

    db_session.refresh(user)
    assert user.role == UserRole.user


def test_demote_unknown_email_exits(db_session) -> None:
    with pytest.raises(SystemExit) as exc_info:
        demote_main("missing@example.com", db=db_session)
    assert exc_info.value.code == 1


def test_demote_non_admin_is_idempotent(db_session) -> None:
    user = _make_user(db_session, "user@example.com", UserRole.user)

    demote_main("user@example.com", db=db_session)

    db_session.refresh(user)
    assert user.role == UserRole.user


def test_demote_last_admin_rejected(db_session) -> None:
    user = _make_user(db_session, "only@example.com", UserRole.admin)

    with pytest.raises(SystemExit) as exc_info:
        demote_main("only@example.com", db=db_session)
    assert exc_info.value.code == 1

    db_session.refresh(user)
    assert user.role == UserRole.admin


def test_demote_one_of_multiple_admins_allowed(db_session) -> None:
    _make_user(db_session, "keep@example.com", UserRole.admin)
    user = _make_user(db_session, "drop@example.com", UserRole.admin)

    demote_main("drop@example.com", db=db_session)

    db_session.refresh(user)
    assert user.role == UserRole.user

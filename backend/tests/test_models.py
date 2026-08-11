from app.models.otp import Otp, OtpPurpose
from app.models.session import Session
from app.models.user import User, UserRole, UserStatus


def test_create_user_session_otp(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="Alice")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.user
    assert user.status == UserStatus.active

    session = Session(user_id=user.id, token_hash="abc", expires_at=user.created_at)
    otp = Otp(purpose=OtpPurpose.register, target=user.email, code_hash="def", expires_at=user.created_at)
    db_session.add_all([session, otp])
    db_session.commit()

    assert session.id is not None
    assert otp.id is not None

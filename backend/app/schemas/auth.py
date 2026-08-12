from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=80)


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_name: str = ""


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ConfirmPasswordResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    nickname: str
    email_verified: bool
    phone: str | None = None
    role: str
    status: str


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PhoneBind(BaseModel):
    phone: str = Field(pattern=r"^\+?[0-9]{6,20}$")


class SessionOut(BaseModel):
    id: str
    device_name: str
    ip: str
    user_agent: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AppOut(BaseModel):
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None


class TwoFaTotpEnable(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    secret: str = Field(min_length=16, max_length=128)


class PasswordConfirm(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class TwoFaSendRequest(BaseModel):
    challenge_id: str


class TwoFaVerifyRequest(BaseModel):
    challenge_id: str
    method: str = Field(pattern=r"^(email_otp|totp|recovery)$")
    code: str = Field(min_length=1, max_length=64)


def serialize_user(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "email_verified": user.email_verified_at is not None,
        "phone": user.phone,
        "role": user.role.value,
        "status": user.status.value,
    }

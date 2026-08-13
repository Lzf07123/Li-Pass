from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=80)


class InviteRegisterRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nickname: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class EmailResendRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_name: str = ""
    remember_me: bool = False


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
    avatar_url: str | None = None
    phone: str | None = None
    role: str
    status: str


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)

    @field_validator("avatar_url")
    @classmethod
    def _validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # 只允许本服务生成的头像路径，或明确的 http(s) 外链；
        # 禁止 "/uploads/avatars/../" 等路径穿越形态。
        if re.fullmatch(
            r"/uploads/avatars/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{32}\.(jpg|png|gif|webp)",
            value,
        ):
            return value
        if value.startswith(("http://", "https://")):
            return value
        raise ValueError("头像地址不合法")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PhoneBind(BaseModel):
    phone: str = Field(pattern=r"^\+?[0-9]{6,20}$")
    code: str = Field(min_length=6, max_length=6)


class SessionOut(BaseModel):
    id: str
    device_name: str
    ip: str
    user_agent: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AdminSessionUserOut(BaseModel):
    id: str
    email: EmailStr
    nickname: str | None
    role: str
    status: str


class AdminSessionOut(BaseModel):
    id: str
    user: AdminSessionUserOut
    auth_method: str
    device_name: str
    ip: str
    user_agent: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AdminSessionListOut(BaseModel):
    items: list[AdminSessionOut]
    total: int


class AppOut(BaseModel):
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None


class TwoFaTotpEnable(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    secret: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z2-7]+$",
    )
    current_password: str = Field(min_length=1, max_length=128)


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
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "role": user.role.value,
        "status": user.status.value,
    }

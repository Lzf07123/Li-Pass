import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OIDCClientSession(Base):
    """门户会话与 OIDC 客户端的登录关系：记录某次门户会话登录过哪些网站。

    sid 不单独存储，直接由 session_id 派生（str(session_id)），与 id_token 的
    sid 声明保持一致，避免两处状态漂移。
    """

    __tablename__ = "oidc_client_sessions"
    __table_args__ = (UniqueConstraint("session_id", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def sid(self) -> str:
        return str(self.session_id)

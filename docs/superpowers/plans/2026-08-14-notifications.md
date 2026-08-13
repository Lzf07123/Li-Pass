# 站内信与自定义邮件通知 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理端统一通知中心（站内信 + 自定义邮件）+ 用户收件箱、头部未读徽章与邮件偏好开关。

**Architecture:** 后端新增 `Notification`/`NotificationRecipient` 两张表，管理端一次发布即展开为每收件人一行（站内信送达），邮件渠道复用现有 SMTP 批量连接逐封渲染占位符发送；用户端通过 `/api/v1/me/messages*` 读已读/删除，前端新增 `/admin/notifications` 标签页与 `/messages` 收件箱页。

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + pytest（后端）；React 19 + Tailwind v4 + Vitest/Testing Library（前端）。

## Global Constraints

- 设计依据：[站内信与自定义邮件通知设计](../../specs/2026-08-14-notifications-design.md)。
- TDD：每个任务先写测试并运行确认失败，再写最小实现；不得先写实现。
- 后端测试命令（在 `backend/` 下）：`.venv/bin/python -m pytest <path> -q`。
- 前端测试命令（在 `frontend/` 下）：`npx vitest run <path>`；lint `npm run lint`；类型检查 `npx tsc -b`。
- 管理端写操作必须记审计；用户只能操作自己的消息（越权返回 404）。
- UI 文案使用中文；新文案风格与现有管理端一致（btn/btn-danger/table-shell/badge）。
- 每个任务完成并全绿后，按任务末尾的 git 命令提交（仅提交本任务涉及文件）。
- 迁移链当前 head：`e3f5a7b9c1d2`；新迁移以此为 `down_revision`。

---

### Task 1: 通知相关配置项

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_config_production.py`

**Interfaces:**
- Produces: `settings.admin_notification_rate_limit`（int, 默认 20）、`settings.admin_notification_rate_window_seconds`（int, 默认 3600）、`settings.notification_max_recipients`（int, 默认 500）、`settings.notification_retention_days`（int, 默认 180）。

- [ ] **Step 1: 写失败测试**

在 `test_config_production.py` 追加：

```python
def test_notification_settings_defaults(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.delenv("ADMIN_NOTIFICATION_RATE_LIMIT", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFICATION_RATE_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("NOTIFICATION_MAX_RECIPIENTS", raising=False)
    monkeypatch.delenv("NOTIFICATION_RETENTION_DAYS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.admin_notification_rate_limit == 20
    assert settings.admin_notification_rate_window_seconds == 3600
    assert settings.notification_max_recipients == 500
    assert settings.notification_retention_days == 180


def test_notification_settings_reject_invalid_values(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("NOTIFICATION_MAX_RECIPIENTS", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
```

确认该测试文件已有 `import pytest`；没有则补上。

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_config_production.py::test_notification_settings_defaults -q`
Expected: FAIL（`AttributeError: admin_notification_rate_limit` 或断言失败）。

- [ ] **Step 3: 最小实现**

在 `config.py` 的字段区（`admin_invite_rate_limit` 附近）加：

```python
    admin_notification_rate_limit: int = 20
    admin_notification_rate_window_seconds: int = 3600
    notification_max_recipients: int = 500
    notification_retention_days: int = 180
```

在 `_validate`（现有校验方法）追加：

```python
        if self.admin_notification_rate_limit < 1 or self.admin_notification_rate_window_seconds < 1:
            raise ValueError(
                "ADMIN_NOTIFICATION_RATE_LIMIT/ADMIN_NOTIFICATION_RATE_WINDOW_SECONDS 必须 ≥1"
            )
        if not 1 <= self.notification_max_recipients <= 10000:
            raise ValueError("NOTIFICATION_MAX_RECIPIENTS 必须在 1–10000 之间")
        if self.notification_retention_days < 1:
            raise ValueError("NOTIFICATION_RETENTION_DAYS 必须 ≥1")
```

（以现有 `_validate` 内的实际缩进与命名位置为准，保持一致风格。）

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_config_production.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/config.py backend/tests/test_config_production.py
git commit -m "feat: 通知中心配置项（频率/上限/保留期）"
```

---

### Task 2: 数据模型与迁移

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/app/models/notification.py`
- Create: `backend/app/models/notification_recipient.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/7c0f1a2b3c4d_add_notifications.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `User.email_notifications: bool`（默认 True）；`Notification(id, title, body, in_site, email, sender_id, recipient_count, email_sent, email_failed, created_at)`；`NotificationRecipient(id, notification_id, user_id, read_at, created_at)`，唯一约束 `(notification_id, user_id)`，索引 `(user_id, created_at)`。

- [ ] **Step 1: 写失败测试**

在 `test_models.py` 追加：

```python
from datetime import datetime, timezone

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.security.passwords import hash_password


def test_notification_models_defaults(db_session) -> None:
    user = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.email_notifications is True

    notification = Notification(
        title="标题", body="正文", in_site=True, email=False, sender_id=user.id
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    assert notification.recipient_count == 0
    assert notification.email_sent == 0
    assert notification.email_failed == 0

    recipient = NotificationRecipient(
        notification_id=notification.id,
        user_id=user.id,
        read_at=datetime.now(timezone.utc),
    )
    db_session.add(recipient)
    db_session.commit()
    assert recipient.read_at is not None
```

（若 `test_models.py` 没有 `db_session` 用例先例，参照 `test_admin_sessions.py` 的 `db_session` 用法。）

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_models.py::test_notification_models_defaults -q`
Expected: FAIL（`ModuleNotFoundError: app.models.notification`）。

- [ ] **Step 3: 实现模型**

`user.py` 在 `email_otp_enabled` 附近加：

```python
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
```

`notification.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    in_site: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    email_sent: Mapped[int] = mapped_column(Integer, default=0)
    email_failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`notification_recipient.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_recipient"
        ),
        Index("ix_notification_recipients_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`models/__init__.py`：导入并在 `__all__` 加入 `Notification`、`NotificationRecipient`。

`alembic/versions/7c0f1a2b3c4d_add_notifications.py`（`down_revision="e3f5a7b9c1d2"`）：

```python
"""add notifications

Revision ID: 7c0f1a2b3c4d
Revises: e3f5a7b9c1d2
Create Date: 2026-08-14 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c0f1a2b3c4d"
down_revision: Union[str, None] = "e3f5a7b9c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("in_site", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sender_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_recipient"
        ),
    )
    op.create_index(
        op.f("ix_notification_recipients_notification_id"),
        "notification_recipients",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_recipients_user_id"),
        "notification_recipients",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_recipients_user_created",
        "notification_recipients",
        ["user_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "users",
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_notifications")
    op.drop_index(
        "ix_notification_recipients_user_created",
        table_name="notification_recipients",
    )
    op.drop_index(
        op.f("ix_notification_recipients_user_id"),
        table_name="notification_recipients",
    )
    op.drop_index(
        op.f("ix_notification_recipients_notification_id"),
        table_name="notification_recipients",
    )
    op.drop_table("notification_recipients")
    op.drop_table("notifications")
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_models.py -q`
Expected: PASS。再运行 `.venv/bin/alembic upgrade head` 于本地开发库验证迁移可执行（无本地库则跳过，交由测试库 `create_all` 覆盖；`create_all` 不会验证迁移脚本，请在可用的开发库上执行）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models backend/alembic/versions/7c0f1a2b3c4d_add_notifications.py backend/tests/test_models.py
git commit -m "feat: 通知与收件人模型及迁移"
```

---

### Task 3: 邮件服务自定义通知方法

**Files:**
- Modify: `backend/app/services/email.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_email_service.py`

**Interfaces:**
- Produces: `EmailService.send_custom_notification(to: str, subject: str, body: str) -> None`；`EmailService.send_custom_notification_batch(items: list[tuple[str, str, str]]) -> list[Exception | None]`（`items` 元素为 `(to, subject, body)`；SMTP 子类复用单连接）。

- [ ] **Step 1: 写失败测试**

在 `test_email_service.py` 追加（参照现有 SMTP 假连接测试的 monkeypatch 方式，复用文件里已有的 socket/stub 结构；若已有 `_fake_smtp` 类，沿用之）：

```python
def test_smtp_custom_notification_sends_rendered_body(monkeypatch) -> None:
    sent = []

    class FakeSMTP:
        def __init__(self, host, port=None, timeout=None):
            sent.append(("connect", host))

        def login(self, user, password):
            sent.append(("login", user))

        def send_message(self, message):
            sent.append(("message", message["Subject"], message.get_content()))

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="u",
        password="p",
        from_addr="noreply@example.com",
        from_name="Portal",
        use_tls=False,
    )
    service.send_custom_notification(
        "bob@example.com", "维护通知", "您好，Bob：今晚维护"
    )
    assert ("message", "维护通知", "您好，Bob：今晚维护") in sent


def test_smtp_custom_notification_batch_reuses_connection(monkeypatch) -> None:
    connects = 0

    class FakeSMTP:
        def __init__(self, host, port=None, timeout=None):
            nonlocal connects
            connects += 1

        def login(self, user, password):
            pass

        def send_message(self, message):
            pass

        def quit(self):
            pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    service = SMTPEmailService(
        host="smtp.example.com",
        port=587,
        username="u",
        password="p",
        from_addr="noreply@example.com",
        from_name="Portal",
        use_tls=False,
    )
    results = service.send_custom_notification_batch(
        [("a@example.com", "s", "b"), ("b@example.com", "s", "b")]
    )
    assert results == [None, None]
    assert connects == 1
```

（若 `SMTPEmailService` 在测试文件中导入方式不同，按现有 import 调整；`use_tls=False` 使 587 分支走明文连接，与现有测试的假类匹配。）

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_email_service.py -q -k custom_notification`
Expected: FAIL（`AttributeError: send_custom_notification`）。

- [ ] **Step 3: 实现**

`EmailService` 抽象类加：

```python
    @abstractmethod
    def send_custom_notification(self, to: str, subject: str, body: str) -> None: ...

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        """默认实现：逐封发送；SMTP 子类复用单条连接。"""
        results: list[Exception | None] = []
        for to, subject, body in items:
            try:
                self.send_custom_notification(to, subject, body)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results
```

`ConsoleEmailService` 加：

```python
    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        print(
            f"[email:{get_settings().email_backend}] custom notification -> "
            f"{to}: {subject}\n{body}"
        )
```

`SMTPEmailService` 加：

```python
    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        self._send_with_retry(to, subject, body)

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        """复用一条 SMTP 连接发送整批自定义通知。"""
        if not items:
            return []
        results: list[Exception | None] = []
        try:
            server = self._connect()
        except Exception as exc:
            return [exc for _ in items]
        try:
            if self.username:
                server.login(self.username, self.password)
            for to, subject, body in items:
                try:
                    server.send_message(self._build_message(to, subject, body))
                    results.append(None)
                except TRANSIENT_SMTP_ERRORS:
                    try:
                        server.close()
                    except Exception:
                        pass
                    try:
                        server = self._connect()
                        if self.username:
                            server.login(self.username, self.password)
                        server.send_message(self._build_message(to, subject, body))
                        results.append(None)
                    except Exception as exc:
                        results.append(exc)
                except Exception as exc:
                    results.append(exc)
        except Exception as exc:
            return [exc for _ in items]
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return results
```

`tests/conftest.py` 的 `CapturingEmailService` 加：

```python
    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        self.messages.append(("custom_notification", to, f"{subject}\n{body}"))

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        results: list[Exception | None] = []
        for to, subject, body in items:
            try:
                self.send_custom_notification(to, subject, body)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_email_service.py tests/test_auth_register.py -q`
Expected: PASS（注册流程仍走 `captured_email`，确认新增抽象方法未破坏其它假服务）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/email.py backend/tests/conftest.py backend/tests/test_email_service.py
git commit -m "feat: 邮件服务支持自定义通知单发与批量发送"
```

---

### Task 4: 管理端发送通知接口

**Files:**
- Create: `backend/app/api/routes/admin_notifications.py`
- Modify: `backend/app/main.py`（注册路由）
- Modify: `backend/app/services/audit.py`（分类 `admin_notification`）
- Test: `backend/tests/test_notifications_admin.py`

**Interfaces:**
- Consumes: Task 1 配置、Task 2 模型、Task 3 `send_custom_notification_batch`、`get_rate_limiter()`、`log_audit()`、`log_rate_limit_rejected_once()`、`get_current_admin`、`get_current_session`。
- Produces: `POST /api/v1/admin/notifications`，请求体 `{"title","body","in_site","email","emails"?}`，响应 `{"id": str, "recipient_count": int, "email_sent": int, "email_failed": int}`。

- [ ] **Step 1: 写失败测试**

新建 `test_notifications_admin.py`：

```python
import uuid

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.security.passwords import hash_password
from tests.test_admin_sessions import login_admin


def make_user(db_session, email, nickname=None, **overrides) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=nickname or email.split("@")[0],
        **overrides,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_send_in_site_notification_to_all_users(client, db_session) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    bob = make_user(db_session, "bob@example.com", "Bob")

    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "维护", "body": "您好，{nickname}", "in_site": True, "email": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_count"] == 3  # alice + bob + 管理员
    assert data["email_sent"] == 0
    assert data["email_failed"] == 0

    notification = db_session.get(Notification, uuid.UUID(data["id"]))
    assert notification is not None
    recipients = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.notification_id == notification.id
        )
    ).all()
    ids = {r.user_id for r in recipients}
    assert alice.id in ids and bob.id in ids
    assert all(r.read_at is None for r in recipients)

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "admin_send_notification")
    )
    assert audit is not None
    assert audit.category == "admin_notification"


def test_send_email_to_specific_users_renders_placeholders(
    client, db_session, captured_email
) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    make_user(db_session, "bob@example.com", "Bob", email_notifications=False)

    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "你好 {nickname}",
            "body": "邮箱：{email}",
            "in_site": False,
            "email": True,
            "emails": ["ALICE@example.com", "bob@example.com"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_count"] == 2
    assert data["email_sent"] == 1  # bob 关闭邮件通知，被跳过
    assert data["email_failed"] == 0

    custom = [m for m in captured_email.messages if m[0] == "custom_notification"]
    assert len(custom) == 1
    assert custom[0][1] == "alice@example.com"
    assert "Alice" in custom[0][2]
    assert "alice@example.com" in custom[0][2]

    # 关闭邮件偏好的用户仍收到站内信（本用例 in_site=False，改为验证下一次全渠道场景）


def test_send_notification_rejects_missing_emails(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "t",
            "body": "b",
            "in_site": True,
            "email": False,
            "emails": ["nobody@example.com"],
        },
    )
    assert response.status_code == 404
    assert "nobody@example.com" in response.json()["detail"]


def test_send_notification_requires_a_channel(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": False, "email": False},
    )
    assert response.status_code == 400


def test_send_notification_hits_rate_limit(client, db_session, monkeypatch) -> None:
    login_admin(client, db_session)
    from app.core.config import get_settings
    from app.services.rate_limit import get_rate_limiter

    limiter = get_rate_limiter()
    monkeypatch.setattr(
        get_settings(), "admin_notification_rate_limit", 0
    )
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": True, "email": False},
    )
    assert response.status_code == 429
    limiter.reset("admin_notification", "testclient")


def test_non_admin_cannot_send_notification(client, captured_email, db_session) -> None:
    from tests.helpers import register_and_login

    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": True, "email": False},
    )
    assert response.status_code == 403
```

（`monkeypatch.setattr(get_settings(), ...)` 只对“每次重新调用 get_settings()”生效；实现中请务必在函数体内 `settings = get_settings()` 再读值，这也是本项目惯例。`testclient` 是 TestClient 默认 IP，与 `login_admin` 的来源 IP 一致。）

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_notifications_admin.py -q`
Expected: FAIL（404/路由不存在）。

- [ ] **Step 3: 实现**

`audit.py` 的 `AUDIT_CATEGORIES` 增加 `"admin_notification"`。

`admin_notifications.py` 完整实现（含发送与 Task 5 的历史接口，本任务只实现 POST 即可，GET 放 Task 5）：

```python
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User, UserStatus
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.email import get_email_service
from app.services.rate_limit import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-notifications"],
    dependencies=[Depends(get_current_admin)],
)


class AdminNotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)
    in_site: bool = True
    email: bool = False
    emails: list[EmailStr] | None = Field(default=None, max_length=500)


def _render(template: str, user: User) -> str:
    return (
        template.replace("{nickname}", user.nickname or "")
        .replace("{email}", user.email)
    )


@router.post("/notifications", response_model=dict)
def send_notification(
    payload: AdminNotificationCreate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not payload.in_site and not payload.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少选择一种发送渠道")

    settings = get_settings()
    ip = request.client.host if request.client else ""
    batch_count = get_rate_limiter().hit(
        "admin_notification",
        ip,
        settings.admin_notification_rate_window_seconds,
    )
    if batch_count > settings.admin_notification_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_send_notification",
            batch_count,
            settings.admin_notification_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            ip=ip,
            detail={"action": "admin_send_notification", "reason": "rate_limit"},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "发送通知过于频繁，请稍后再试"
        )

    if payload.emails is not None:
        emails = list(
            dict.fromkeys(email.lower() for email in payload.emails)
        )
        if len(emails) > settings.notification_max_recipients:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"单次最多发送给 {settings.notification_max_recipients} 个用户",
            )
        users = db.scalars(
            select(User).where(
                User.email.in_(emails),
                User.status == UserStatus.active,
            )
        ).all()
        found = {user.email: user for user in users}
        missing = [email for email in emails if email not in found]
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"部分邮箱不存在或未启用：{','.join(missing[:5])}",
            )
        recipients = users
    else:
        recipient_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.status == UserStatus.active)
            )
            or 0
        )
        if recipient_count == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "没有可接收通知的用户"
            )
        if recipient_count > settings.notification_max_recipients:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"用户总数超过单次上限（{settings.notification_max_recipients}），"
                "请指定邮箱分批发送",
            )
        recipients = db.scalars(
            select(User).where(User.status == UserStatus.active)
        ).all()

    notification = Notification(
        title=payload.title,
        body=payload.body,
        in_site=payload.in_site,
        email=payload.email,
        sender_id=actor.id,
        recipient_count=len(recipients),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    for user in recipients:
        db.add(
            NotificationRecipient(
                notification_id=notification.id, user_id=user.id
            )
        )
    db.commit()

    email_sent = 0
    email_failed = 0
    failed_emails: list[str] = []
    if payload.email:
        targets = [user for user in recipients if user.email_notifications]
        items = [
            (
                user.email,
                _render(payload.title, user),
                _render(payload.body, user),
            )
            for user in targets
        ]
        results = get_email_service().send_custom_notification_batch(items)
        for user, result in zip(targets, results):
            if result is None:
                email_sent += 1
            else:
                email_failed += 1
                failed_emails.append(user.email)
                logger.error(
                    "通知邮件发送失败：%s error=%s", user.email, result
                )
        notification.email_sent = email_sent
        notification.email_failed = email_failed
        db.commit()

    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_send_notification",
        category="admin_notification",
        target_type="notification",
        target_id=str(notification.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={
            "title": payload.title,
            "in_site": payload.in_site,
            "email": payload.email,
            "recipient_count": len(recipients),
            "email_sent": email_sent,
            "email_failed": email_failed,
            "failed_emails": failed_emails[:20],
        },
    )
    return {
        "id": str(notification.id),
        "recipient_count": len(recipients),
        "email_sent": email_sent,
        "email_failed": email_failed,
    }
```

`main.py` 注册：`from app.api.routes import admin_notifications as admin_notifications_routes`，并在 `app.include_router(...)` 区域照现有顺序加入 `app.include_router(admin_notifications_routes.router)`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_notifications_admin.py -q`
Expected: PASS（rate limit 用例若因 monkeypatch 方式失败，按“函数内 get_settings()”调整实现后重跑；不要改测试语义）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/routes/admin_notifications.py backend/app/main.py backend/app/services/audit.py backend/tests/test_notifications_admin.py
git commit -m "feat: 管理端发送站内信/自定义邮件通知接口"
```

---

### Task 5: 管理端通知历史接口

**Files:**
- Modify: `backend/app/api/routes/admin_notifications.py`
- Test: `backend/tests/test_notifications_admin.py`

**Interfaces:**
- Produces: `GET /api/v1/admin/notifications?offset&limit` → `{"items": [...], "total": int}`；条目 `{"id","title","in_site","email","recipient_count","email_sent","email_failed","created_at","sender_email","sender_nickname"}`。

- [ ] **Step 1: 写失败测试**

在 `test_notifications_admin.py` 追加：

```python
def test_list_notifications_history(client, db_session) -> None:
    login_admin(client, db_session)
    client.post(
        "/api/v1/admin/notifications",
        json={"title": "第一条", "body": "b", "in_site": True, "email": False},
    )
    client.post(
        "/api/v1/admin/notifications",
        json={"title": "第二条", "body": "b", "in_site": True, "email": False},
    )

    response = client.get("/api/v1/admin/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert [item["title"] for item in data["items"]] == ["第二条", "第一条"]
    first = data["items"][0]
    assert first["in_site"] is True
    assert first["email"] is False
    assert first["sender_email"] == "admin@example.com"
    assert first["recipient_count"] >= 1
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_notifications_admin.py::test_list_notifications_history -q`
Expected: FAIL（404）。

- [ ] **Step 3: 实现**

在 `admin_notifications.py` 追加：

```python
@router.get("/notifications", response_model=dict)
def list_notifications(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    base = select(Notification, User).join(
        User, Notification.sender_id == User.id, isouter=True
    )
    total = (
        db.scalar(select(func.count()).select_from(Notification)) or 0
    )
    rows = db.execute(
        base.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(notification.id),
                "title": notification.title,
                "in_site": notification.in_site,
                "email": notification.email,
                "recipient_count": notification.recipient_count,
                "email_sent": notification.email_sent,
                "email_failed": notification.email_failed,
                "created_at": notification.created_at,
                "sender_email": sender.email if sender else None,
                "sender_nickname": sender.nickname if sender else None,
            }
            for notification, sender in rows
        ],
        "total": total,
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_notifications_admin.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/routes/admin_notifications.py backend/tests/test_notifications_admin.py
git commit -m "feat: 管理端通知发送历史接口"
```

---

### Task 6: 用户站内信接口

**Files:**
- Create: `backend/app/api/routes/messages.py`
- Modify: `backend/app/main.py`（注册路由）
- Test: `backend/tests/test_messages.py`

**Interfaces:**
- Consumes: Task 2 模型、`get_current_user`。
- Produces:
  - `GET /api/v1/me/messages?offset&limit` → `{"items": [{"id","title","body","sent_at","read"}], "total": int, "unread": int}`
  - `GET /api/v1/me/messages/unread-count` → `{"unread": int}`
  - `POST /api/v1/me/messages/{message_id}/read` → 204
  - `POST /api/v1/me/messages/read-all` → `{"updated": int}`
  - `DELETE /api/v1/me/messages/{message_id}` → 204

- [ ] **Step 1: 写失败测试**

新建 `test_messages.py`：

```python
import uuid

from sqlalchemy import select

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.security.passwords import hash_password


def make_user(db_session, email) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=email.split("@")[0],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client, email) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )


def send(db_session, sender: User, targets: list[User]) -> Notification:
    notification = Notification(
        title="维护通知",
        body="您好",
        in_site=True,
        email=False,
        sender_id=sender.id,
        recipient_count=len(targets),
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    for user in targets:
        db_session.add(
            NotificationRecipient(
                notification_id=notification.id, user_id=user.id
            )
        )
    db_session.commit()
    return notification


def test_list_messages_and_unread_count(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    send(db_session, admin, [alice, bob])
    login(client, "alice@example.com")

    data = client.get("/api/v1/me/messages").json()
    assert data["total"] == 1
    assert data["unread"] == 1
    assert data["items"][0]["title"] == "维护通知"
    assert data["items"][0]["read"] is False
    assert client.get("/api/v1/me/messages/unread-count").json() == {
        "unread": 1
    }


def test_mark_read_read_all_and_delete_own_messages(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    first = send(db_session, admin, [alice, bob])
    second = send(db_session, admin, [alice])
    login(client, "alice@example.com")

    mine = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == alice.id,
            NotificationRecipient.notification_id == first.id,
        )
    ).one()
    assert client.post(f"/api/v1/me/messages/{mine.id}/read").status_code == 204

    result = client.post("/api/v1/me/messages/read-all").json()
    assert result["updated"] == 1  # 第一条已读，剩第二条
    assert client.get("/api/v1/me/messages/unread-count").json() == {
        "unread": 0
    }

    other = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == alice.id,
            NotificationRecipient.notification_id == second.id,
        )
    ).one()
    assert (
        client.delete(f"/api/v1/me/messages/{other.id}").status_code == 204
    )
    assert client.get("/api/v1/me/messages").json()["total"] == 1


def test_cannot_touch_other_users_messages(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    send(db_session, admin, [alice, bob])
    login(client, "alice@example.com")
    bobs = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == bob.id
        )
    ).one()
    assert (
        client.post(f"/api/v1/me/messages/{bobs.id}/read").status_code == 404
    )
    assert (
        client.delete(f"/api/v1/me/messages/{bobs.id}").status_code == 404
    )


def test_requires_auth(client) -> None:
    assert client.get("/api/v1/me/messages").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_messages.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 实现**

`messages.py`：

```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User

router = APIRouter(prefix="/api/v1/me", tags=["messages"])


def _serialize(recipient: NotificationRecipient, notification: Notification) -> dict:
    return {
        "id": str(recipient.id),
        "title": notification.title,
        "body": notification.body,
        "sent_at": notification.created_at,
        "read": recipient.read_at is not None,
    }


@router.get("/messages", response_model=dict)
def list_messages(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    base = (
        select(NotificationRecipient, Notification)
        .join(
            Notification,
            NotificationRecipient.notification_id == Notification.id,
        )
        .where(NotificationRecipient.user_id == user.id)
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .where(NotificationRecipient.user_id == user.id)
        )
        or 0
    )
    unread = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .where(
                NotificationRecipient.user_id == user.id,
                NotificationRecipient.read_at.is_(None),
            )
        )
        or 0
    )
    rows = db.execute(
        base.order_by(NotificationRecipient.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [_serialize(r, n) for r, n in rows],
        "total": total,
        "unread": unread,
    }


@router.get("/messages/unread-count", response_model=dict)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    count = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .where(
                NotificationRecipient.user_id == user.id,
                NotificationRecipient.read_at.is_(None),
            )
        )
        or 0
    )
    return {"unread": count}


def _get_own(db: Session, user: User, message_id: uuid.UUID):
    recipient = db.scalar(
        select(NotificationRecipient).where(
            NotificationRecipient.id == message_id,
            NotificationRecipient.user_id == user.id,
        )
    )
    if recipient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "消息不存在")
    return recipient


@router.post("/messages/{message_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    recipient = _get_own(db, user, message_id)
    if recipient.read_at is None:
        recipient.read_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/messages/read-all", response_model=dict)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = db.execute(
        update(NotificationRecipient)
        .where(
            NotificationRecipient.user_id == user.id,
            NotificationRecipient.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"updated": result.rowcount or 0}


@router.delete(
    "/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_message(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    recipient = _get_own(db, user, message_id)
    db.delete(recipient)
    db.commit()
```

`main.py` 注册 `messages_routes.router`（与 `users` 路由同一区域）。

**注意路由顺序**：`/messages/read-all`（POST）与 `/messages/{message_id}/read`（POST）路径不同，无冲突；`/messages/unread-count`（GET）与 `/messages/{...}`（POST/DELETE）方法不同，无冲突。按上列顺序声明即可。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_messages.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/routes/messages.py backend/app/main.py backend/tests/test_messages.py
git commit -m "feat: 用户站内信列表/已读/删除接口"
```

---

### Task 7: 用户邮件通知偏好

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/routes/users.py`
- Test: `backend/tests/test_user_center.py`（或 `test_auth_register.py` 中 `PUT /me` 的现有测试文件）

**Interfaces:**
- Consumes: Task 2 `User.email_notifications`。
- Produces: `UserOut.email_notifications: bool`；`ProfileUpdate.email_notifications: bool | None`；`PUT /api/v1/me` 支持关闭/开启。

- [ ] **Step 1: 写失败测试**

在 `PUT /me` 既有测试文件追加：

```python
def test_update_profile_email_notifications(client, captured_email, db_session) -> None:
    from tests.helpers import register_and_login

    register_and_login(client, captured_email)
    me = client.get("/api/v1/me").json()
    assert me["email_notifications"] is True

    updated = client.put(
        "/api/v1/me", json={"email_notifications": False}
    ).json()
    assert updated["email_notifications"] is False
    again = client.put("/api/v1/me", json={"nickname": "New"}).json()
    assert again["email_notifications"] is False  # 未传字段不重置
    assert again["nickname"] == "New"
```

（`register_and_login` 需 `captured_email`；该文件若无此 fixture，参照 `test_admin_sessions.py` 的 `test_non_admin_cannot_access_session_monitoring` 引入。）

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_user_center.py -q -k email_notifications`
Expected: FAIL（断言或 KeyError）。

- [ ] **Step 3: 实现**

`schemas/auth.py`：

```python
class UserOut(BaseModel):
    ...
    email_notifications: bool


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    email_notifications: bool | None = None
```

`serialize_user` 加 `"email_notifications": user.email_notifications`。

`users.py` 的 `update_profile` 加：

```python
    if payload.email_notifications is not None:
        user.email_notifications = payload.email_notifications
```

并让 `log_audit` 的 detail 增加 `"email_notifications_changed": payload.email_notifications is not None`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_user_center.py -q`
Expected: PASS（若其它用例断言了 `UserOut` 全字段或 profile 更新 payload，需同步补 `email_notifications`，属预期内的测试维护）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/auth.py backend/app/api/routes/users.py backend/tests/test_user_center.py
git commit -m "feat: 用户可开关邮件通知偏好"
```

---

### Task 8: 已读消息保留清理

**Files:**
- Modify: `backend/app/services/maintenance.py`
- Test: `backend/tests/test_maintenance.py`

**Interfaces:**
- Consumes: Task 2 模型、Task 1 `notification_retention_days`。
- Produces: `cleanup_expired_ephemeral_rows` 返回值增加键 `"notification_recipients"`。

- [ ] **Step 1: 写失败测试**

在 `test_maintenance.py` 追加：

```python
from datetime import datetime, timedelta, timezone

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.security.passwords import hash_password
from app.services.maintenance import cleanup_expired_ephemeral_rows


def test_cleanup_read_notifications_after_retention(db_session) -> None:
    user = User(
        email="a@example.com", password_hash=hash_password("password123")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    notification = Notification(
        title="t", body="b", in_site=True, email=False, sender_id=user.id
    )
    db_session.add(notification)
    db_session.commit()
    old = NotificationRecipient(
        notification_id=notification.id,
        user_id=user.id,
        read_at=datetime.now(timezone.utc) - timedelta(days=400),
    )
    unread = NotificationRecipient(
        notification_id=notification.id, user_id=user.id
    )
    db_session.add_all([old, unread])
    db_session.commit()

    counts = cleanup_expired_ephemeral_rows(db_session)
    assert counts["notification_recipients"] == 1
    remaining = db_session.scalars(
        select(NotificationRecipient)
    ).all()
    assert [row.id for row in remaining] == [unread.id]
```

（若文件未导入 `select`/`NotificationRecipient`，在顶部补 import。）

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_maintenance.py -q -k notification`
Expected: FAIL（KeyError 或断言）。

- [ ] **Step 3: 实现**

`maintenance.py`：导入 `NotificationRecipient`；在函数内加：

```python
    notification_cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().notification_retention_days
    )
    notification_result = db.execute(
        delete(NotificationRecipient).where(
            NotificationRecipient.read_at.is_not(None),
            NotificationRecipient.read_at < notification_cutoff,
        )
    )
```

返回 dict 加 `"notification_recipients": notification_result.rowcount or 0`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_maintenance.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/maintenance.py backend/tests/test_maintenance.py
git commit -m "feat: 已读站内信按保留期自动清理"
```

---

### Task 9: 审计分类前端标签

**Files:**
- Modify: `frontend/src/pages/AdminAuditPanel.tsx`
- Test: `frontend/src/__tests__/AdminAuditPanel.test.tsx`

**Interfaces:**
- Consumes: Task 4 的后端分类 `admin_notification`。
- Produces: 审计筛选下拉出现「通知管理」选项。

- [ ] **Step 1: 写失败测试**

在 `AdminAuditPanel.test.tsx` 追加：

```ts
it("筛选分类包含通知管理", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
  );
  renderWithProviders(<AdminAuditPanel />);
  await waitFor(() =>
    expect(screen.getByRole("combobox")).toBeInTheDocument()
  );
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "admin_notification" },
  });
  expect(
    (screen.getByRole("combobox") as HTMLSelectElement).value
  ).toBe("admin_notification");
});
```

（以现有筛选下拉的测试方式为准：若现有测试用 `getByLabelText` 或不同交互，先看该文件现有用例再照写。）

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/__tests__/AdminAuditPanel.test.tsx`
Expected: FAIL（找不到 `admin_notification` 选项）。

- [ ] **Step 3: 实现**

`CATEGORY_LABELS` 加一行：`admin_notification: "通知管理",`（放在 `admin_settings` 之后）。

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run src/__tests__/AdminAuditPanel.test.tsx && npm run lint && npx tsc -b`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/AdminAuditPanel.tsx frontend/src/__tests__/AdminAuditPanel.test.tsx
git commit -m "feat: 审计筛选新增通知管理分类"
```

---

### Task 10: 前端 API 类型与客户端

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces:
  - `AdminNotificationOut`、`AdminNotificationListOut`、`SendNotificationResult`、`MessageOut`、`MessageListOut`（字段与 Task 4/5/6 响应一致）。
  - `UserOut.email_notifications: boolean`。
  - `adminNotificationsApi.create(data)` / `.list(offset, limit)`；`userMessagesApi.list(offset, limit)` / `.unreadCount()` / `.markRead(id)` / `.markAllRead()` / `.remove(id)`。

- [ ] **Step 1: 写失败测试**

新建 `frontend/src/__tests__/ApiClientNotifications.test.ts`：

```ts
import { describe, expect, it, vi } from "vitest";

import { adminNotificationsApi, userMessagesApi } from "../api/client";

describe("通知相关 API", () => {
  it("发送通知请求体正确", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "n1", recipient_count: 2, email_sent: 1, email_failed: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await adminNotificationsApi.create({
      title: "t",
      body: "b",
      in_site: true,
      email: true,
      emails: ["a@example.com"],
    });
    expect(result.recipient_count).toBe(2);
    const [, init] = fetchMock.mock.calls[0] as [unknown, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      title: "t",
      body: "b",
      in_site: true,
      email: true,
      emails: ["a@example.com"],
    });
  });

  it("标记全部已读调用正确端点", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ updated: 3 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await userMessagesApi.markAllRead();
    expect(result.updated).toBe(3);
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/api/v1/me/messages/read-all"
    );
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/__tests__/ApiClientNotifications.test.ts`
Expected: FAIL（`adminNotificationsApi` 未定义）。

- [ ] **Step 3: 实现**

`types.ts` 追加：

```ts
export interface AdminNotificationOut {
  id: string;
  title: string;
  in_site: boolean;
  email: boolean;
  recipient_count: number;
  email_sent: number;
  email_failed: number;
  created_at: string;
  sender_email: string | null;
  sender_nickname: string | null;
}

export interface AdminNotificationListOut {
  items: AdminNotificationOut[];
  total: number;
}

export interface SendNotificationResult {
  id: string;
  recipient_count: number;
  email_sent: number;
  email_failed: number;
}

export interface MessageOut {
  id: string;
  title: string;
  body: string;
  sent_at: string;
  read: boolean;
}

export interface MessageListOut {
  items: MessageOut[];
  total: number;
  unread: number;
}
```

`UserOut` 加 `email_notifications: boolean;`。

`client.ts` 的 import 列表补 `AdminNotificationListOut`、`MessageListOut`、`SendNotificationResult`；追加：

```ts
export const adminNotificationsApi = {
  create: (data: {
    title: string;
    body: string;
    in_site: boolean;
    email: boolean;
    emails?: string[];
  }) =>
    api<SendNotificationResult>("/api/v1/admin/notifications", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  list: (offset = 0, limit = 100) =>
    api<AdminNotificationListOut>(
      `/api/v1/admin/notifications?offset=${offset}&limit=${limit}`
    ),
};

export const userMessagesApi = {
  list: (offset = 0, limit = 100) =>
    api<MessageListOut>(
      `/api/v1/me/messages?offset=${offset}&limit=${limit}`
    ),
  unreadCount: () =>
    api<{ unread: number }>("/api/v1/me/messages/unread-count"),
  markRead: (id: string) =>
    api<void>(`/api/v1/me/messages/${id}/read`, { method: "POST" }),
  markAllRead: () =>
    api<{ updated: number }>("/api/v1/me/messages/read-all", {
      method: "POST",
    }),
  remove: (id: string) =>
    api<void>(`/api/v1/me/messages/${id}`, { method: "DELETE" }),
};
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run src/__tests__/ApiClientNotifications.test.ts && npx tsc -b`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/__tests__/ApiClientNotifications.test.ts
git commit -m "feat: 通知相关 API 类型与客户端"
```

---

### Task 11: 管理端「通知管理」面板与路由

**Files:**
- Create: `frontend/src/pages/AdminNotificationsPanel.tsx`
- Modify: `frontend/src/pages/AdminPage.tsx`
- Test: `frontend/src/__tests__/AdminNotificationsPanel.test.tsx`

**Interfaces:**
- Consumes: Task 10 `adminNotificationsApi`。
- Produces: `/admin/notifications` 标签页。

- [ ] **Step 1: 写失败测试**

新建 `AdminNotificationsPanel.test.tsx`（结构参照 `AdminSessionsPanel.test.tsx`）：

```ts
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminNotificationsPanel } from "../pages/AdminNotificationsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function historyResponse(items: unknown[] = []) {
  return new Response(JSON.stringify({ items, total: items.length }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminNotificationsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染历史列表", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        historyResponse([
          {
            id: "n1",
            title: "维护通知",
            in_site: true,
            email: false,
            recipient_count: 2,
            email_sent: 0,
            email_failed: 0,
            created_at: "2026-08-14T10:00:00Z",
            sender_email: "admin@example.com",
            sender_nickname: "Admin",
          },
        ])
      )
    );
    renderWithProviders(<AdminNotificationsPanel />);
    await waitFor(() =>
      expect(screen.getByText("维护通知")).toBeInTheDocument()
    );
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
  });

  it("未选渠道时提示并阻止发送", async () => {
    const fetchMock = vi.fn().mockResolvedValue(historyResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "t" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "b" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "站内信" }));
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() =>
      expect(screen.getByText("至少选择一种发送渠道")).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/admin/notifications")
      )
    ).toBe(false);
  });

  it("发送通知提交正确请求体", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "n1",
              recipient_count: 1,
              email_sent: 1,
              email_failed: 0,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(historyResponse());
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "你好 {nickname}" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "通知内容" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "邮件" }));
    fireEvent.click(screen.getByRole("radio", { name: "指定用户" }));
    fireEvent.change(screen.getByLabelText("收件人邮箱（每行一个）"), {
      target: { value: "a@example.com\nb@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).includes("/admin/notifications") &&
          init?.method === "POST"
      );
      expect(post).toBeDefined();
      const body = JSON.parse(
        String((post as [unknown, RequestInit])[1].body)
      );
      expect(body.emails).toEqual(["a@example.com", "b@example.com"]);
      expect(body.in_site).toBe(true);
      expect(body.email).toBe(true);
    });
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/__tests__/AdminNotificationsPanel.test.tsx`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

`AdminNotificationsPanel.tsx`：

```tsx
import { useEffect, useState } from "react";

import { adminNotificationsApi } from "../api/client";
import type { AdminNotificationOut } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function AdminNotificationsPanel() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [inSite, setInSite] = useState(true);
  const [email, setEmail] = useState(false);
  const [scope, setScope] = useState<"all" | "specific">("all");
  const [emailsText, setEmailsText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [history, setHistory] = useState<AdminNotificationOut[]>([]);
  const [total, setTotal] = useState(0);
  const toast = useToast();

  const load = (offset = 0, append = false) =>
    adminNotificationsApi
      .list(offset, 100)
      .then(({ items, total: nextTotal }) => {
        setHistory((prev) => (append ? [...prev, ...items] : items));
        setTotal(nextTotal);
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败")
      );

  useEffect(() => {
    void load();
  }, []);

  const sendAction = useAsyncAction(
    async () => {
      const emails =
        scope === "specific"
          ? emailsText
              .split(/[\n,，;；\s]+/)
              .map((email) => email.trim())
              .filter(Boolean)
          : undefined;
      const result = await adminNotificationsApi.create({
        title: title.trim(),
        body: body.trim(),
        in_site: inSite,
        email,
        ...(emails ? { emails } : {}),
      });
      setTitle("");
      setBody("");
      setEmailsText("");
      await load();
      toast.success(
        `已发送给 ${result.recipient_count} 人，邮件成功 ${result.email_sent} 封`
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "发送失败"),
    }
  );

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inSite && !email) {
      setFormError("至少选择一种发送渠道");
      return;
    }
    if (!title.trim() || !body.trim()) {
      setFormError("标题和正文不能为空");
      return;
    }
    if (scope === "specific") {
      const emails = emailsText
        .split(/[\n,，;；\s]+/)
        .map((email) => email.trim())
        .filter(Boolean);
      if (emails.length === 0) {
        setFormError("请填写收件人邮箱");
        return;
      }
      const bad = emails.find((item) => !EMAIL_RE.test(item));
      if (bad) {
        setFormError(`邮箱格式不正确：${bad}`);
        return;
      }
    }
    setFormError(null);
    void sendAction.run();
  }

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">通知管理</h2>
      <form onSubmit={submit} className="card space-y-4 p-6">
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">发送渠道</span>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={inSite}
              onChange={(e) => setInSite(e.target.checked)}
            />
            站内信
          </label>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={email}
              onChange={(e) => setEmail(e.target.checked)}
            />
            邮件（关闭邮件通知的用户自动跳过）
          </label>
        </div>
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">收件人</span>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="scope"
              checked={scope === "all"}
              onChange={() => setScope("all")}
            />
            全部用户
          </label>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="scope"
              checked={scope === "specific"}
              onChange={() => setScope("specific")}
            />
            指定用户
          </label>
          {scope === "specific" && (
            <textarea
              aria-label="收件人邮箱（每行一个）"
              value={emailsText}
              onChange={(e) => setEmailsText(e.target.value)}
              placeholder={"每行一个邮箱，例如：\na@example.com\nb@example.com"}
              className="input min-h-24 w-full"
            />
          )}
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">
            标题
            <input
              aria-label="标题"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
              placeholder="例如：平台维护通知"
              className="input mt-1 w-full"
            />
          </label>
          <label className="block text-sm font-medium text-foreground">
            正文
            <textarea
              aria-label="正文"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={5000}
              rows={5}
              placeholder={"支持占位符：{nickname} 昵称、{email} 邮箱"}
              className="input mt-1 w-full"
            />
          </label>
        </div>
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <AsyncButton
          type="submit"
          status={sendAction.status}
          className="btn btn-primary"
        >
          发送通知
        </AsyncButton>
      </form>

      <div className="table-shell">
        <table className="w-full">
          <thead>
            <tr>
              <th className="whitespace-nowrap">时间</th>
              <th className="whitespace-nowrap">标题</th>
              <th className="whitespace-nowrap">渠道</th>
              <th className="whitespace-nowrap">收件人</th>
              <th className="whitespace-nowrap">邮件</th>
              <th className="whitespace-nowrap">发送人</th>
            </tr>
          </thead>
          <tbody>
            {history.map((item) => (
              <tr key={item.id}>
                <td className="whitespace-nowrap">
                  {formatTime(item.created_at)}
                </td>
                <td className="max-w-[16rem] truncate">{item.title}</td>
                <td>
                  <span className="mr-1 badge badge-muted">
                    {item.in_site ? "站内信" : ""}
                  </span>
                  {item.email && (
                    <span className="badge badge-muted">邮件</span>
                  )}
                </td>
                <td>{item.recipient_count} 人</td>
                <td>
                  {item.email
                    ? `成功 ${item.email_sent} / 失败 ${item.email_failed}`
                    : "—"}
                </td>
                <td className="truncate">
                  {item.sender_email || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {history.length < total && (
          <button
            type="button"
            className="btn btn-secondary w-full"
            onClick={() => void load(history.length, true)}
          >
            加载更多
          </button>
        )}
      </div>
      {total === 0 && (
        <p className="text-sm text-muted">还没有发送记录。</p>
      )}
    </section>
  );
}
```

`AdminPage.tsx`：`TABS` 增加 `{ key: "notifications", label: "通知管理" }`；import 并在 `tab === "notifications" && <AdminNotificationsPanel />` 渲染。

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run src/__tests__/AdminNotificationsPanel.test.tsx src/__tests__/AdminPage.test.tsx && npm run lint && npx tsc -b`
Expected: PASS（`AdminPage.test.tsx` 若断言标签数量/列表，同步更新为 6 个标签）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/AdminNotificationsPanel.tsx frontend/src/pages/AdminPage.tsx frontend/src/__tests__/AdminNotificationsPanel.test.tsx frontend/src/__tests__/AdminPage.test.tsx
git commit -m "feat: 管理端通知管理面板"
```

---

### Task 12: 用户收件箱页、路由与头部铃铛

**Files:**
- Create: `frontend/src/pages/MessagesPage.tsx`
- Create: `frontend/src/components/MessageBell.tsx`
- Modify: `frontend/src/components/bits/LineIcon.tsx`（新增 `mail` 图标）
- Modify: `frontend/src/components/AppHeader.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/__tests__/MessagesPage.test.tsx`
- Modify: `frontend/src/__tests__/DashboardPage.test.tsx`、`DashboardTwofa.test.tsx`、`AdminPage.test.tsx`（补 unread-count 响应，见下）

**Interfaces:**
- Consumes: Task 10 `userMessagesApi`。
- Produces: `/messages` 页面；`AppHeader` 固定渲染 `MessageBell`。

- [ ] **Step 1: 写失败测试**

新建 `MessagesPage.test.tsx`：

```tsx
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessagesPage } from "../pages/MessagesPage";
import { renderWithProviders } from "../test/renderWithProviders";

function messagesResponse(items: unknown[], unread = 0) {
  return new Response(JSON.stringify({ items, total: items.length, unread }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MessagesPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染未读消息并可标记已读", async () => {
    const item = {
      id: "m1",
      title: "维护通知",
      body: "正文",
      sent_at: "2026-08-14T10:00:00Z",
      read: false,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/read")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/api/v1/me")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "u1",
              email: "a@example.com",
              nickname: "Alice",
              email_verified: true,
              email_notifications: true,
              avatar_url: null,
              phone: null,
              role: "user",
              status: "active",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(messagesResponse([item], 1));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<MessagesPage />, ["/messages"]);

    await waitFor(() => expect(screen.getByText("维护通知")).toBeInTheDocument());
    expect(screen.getByText(/未读 1 条/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "标记已读" }));
    await waitFor(() =>
      expect(screen.getByText(/未读 0 条/)).toBeInTheDocument()
    );
  });

  it("全部已读与删除调用对应端点", async () => {
    const items = [
      { id: "m1", title: "一", body: "b", sent_at: "2026-08-14T10:00:00Z", read: false },
      { id: "m2", title: "二", body: "b", sent_at: "2026-08-14T09:00:00Z", read: false },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/read-all")) {
        return Promise.resolve(
          new Response(JSON.stringify({ updated: 2 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/api/v1/me")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "u1",
              email: "a@example.com",
              nickname: "Alice",
              email_verified: true,
              email_notifications: true,
              avatar_url: null,
              phone: null,
              role: "user",
              status: "active",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(messagesResponse(items, 2));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<MessagesPage />, ["/messages"]);
    await waitFor(() => expect(screen.getByText("一")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "全部已读" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("/read-all")
        )
      ).toBe(true)
    );
    fireEvent.click(screen.getAllByRole("button", { name: "删除" })[0]);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/api/v1/me/messages/m1") &&
            init?.method === "DELETE"
        )
      ).toBe(true)
    );
  });
});
```

注意：`MessagesPage` 会先 `authApi.me()` 校验登录。上面的 fetch mock 用 `/api/v1/me` 前缀返回用户对象，消息接口 URL 是 `/api/v1/me/messages`，需要把用户判断放在 `messages` 判断**之后**（URL 包含判断按长度优先，先匹配 messages）。测试代码已按此顺序书写。

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/__tests__/MessagesPage.test.tsx`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

`LineIcon.tsx`：`LineIconName` 增加 `"mail"`，`ICON_PATHS` 增加：

```tsx
  mail: (
    <>
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </>
  ),
```

`MessageBell.tsx`：

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { userMessagesApi } from "../api/client";
import { LineIcon } from "./bits/LineIcon";

export function MessageBell() {
  const [unread, setUnread] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    userMessagesApi
      .unreadCount()
      .then((data) => {
        if (!cancelled) setUnread(data.unread);
      })
      .catch(() => {
        if (!cancelled) setUnread(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (unread === null) return null;
  return (
    <Link
      to="/messages"
      className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
      aria-label={unread > 0 ? `站内信，${unread} 条未读` : "站内信"}
    >
      <LineIcon name="mail" className="h-5 w-5" />
      {unread > 0 && (
        <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
```

`AppHeader.tsx`：import `MessageBell`，在 `<ThemeToggle />` 前渲染 `<MessageBell />`。

`MessagesPage.tsx`：

```tsx
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi, userMessagesApi } from "../api/client";
import type { MessageOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { FloatingBackground } from "../components/FloatingBackground";
import { PageSkeleton } from "../components/PageSkeleton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function MessagesPage() {
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<MessageOut[]>([]);
  const [unread, setUnread] = useState(0);
  const toast = useToast();
  const navigate = useNavigate();

  const load = useCallback(() => {
    userMessagesApi
      .list(0, 100)
      .then((data) => {
        setItems(data.items);
        setUnread(data.unread);
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败")
      );
  }, [toast]);

  useEffect(() => {
    authApi
      .me()
      .then(() => {
        setReady(true);
        load();
      })
      .catch(() => navigate("/login"));
  }, [load, navigate]);

  const markReadAction = useAsyncAction(async (id: string) => {
    await userMessagesApi.markRead(id);
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, read: true } : item))
    );
    setUnread((value) => Math.max(0, value - 1));
  }, { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") });

  const markAllAction = useAsyncAction(async () => {
    const result = await userMessagesApi.markAllRead();
    setItems((prev) => prev.map((item) => ({ ...item, read: true })));
    setUnread(0);
    toast.success(`已将 ${result.updated} 条消息标记为已读`);
  }, { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") });

  const removeAction = useAsyncAction(async (id: string) => {
    await userMessagesApi.remove(id);
    setItems((prev) => prev.filter((item) => item.id !== id));
    toast.success("消息已删除");
  }, { onError: (err) => toast.error(err instanceof Error ? err.message : "删除失败") });

  if (!ready) {
    return <PageSkeleton title="站内信" />;
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      <FloatingBackground theme="auto" transparent shapeCount={4} opacity={0.5} />
      <AppHeader
        title="站内信"
        actions={
          <Link to="/" className="btn btn-secondary">
            返回用户中心
          </Link>
        }
      />
      <main className="relative mx-auto w-full max-w-3xl flex-1 space-y-4 px-4 py-8 sm:px-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">未读 {unread} 条</p>
          {unread > 0 && (
            <button
              type="button"
              onClick={() => void markAllAction.run()}
              className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
            >
              全部已读
            </button>
          )}
        </div>
        {items.length === 0 ? (
          <div className="card p-10 text-center text-sm text-muted">
            暂无站内信
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.id}
                className={`card space-y-2 p-4 ${item.read ? "" : "border-primary/40"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-foreground">{item.title}</p>
                    <p className="text-xs text-muted">{formatTime(item.sent_at)}</p>
                  </div>
                  {!item.read && (
                    <span className="badge badge-primary">未读</span>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm text-foreground">
                  {item.body}
                </p>
                <div className="flex gap-2">
                  {!item.read && (
                    <button
                      type="button"
                      onClick={() => void markReadAction.run(item.id)}
                      className="btn-link text-xs"
                    >
                      标记已读
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void removeAction.run(item.id)}
                    className="btn-link text-xs text-destructive"
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
```

`App.tsx`：lazy import `MessagesPage`；在 `Route path="/"` 前加 `<Route path="/messages" element={<MessagesPage />} />`。

**同步既有测试**：`AppHeader` 现在渲染 `MessageBell`，其 `useEffect` 会在子组件挂载时先于页面数据请求发起一次 `GET /api/v1/me/messages/unread-count`。对以下用 `mockResolvedValueOnce` 顺序断言的测试，在序列**最前面**补一条：

```ts
.mockResolvedValueOnce(
  new Response(JSON.stringify({ unread: 0 }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
)
```

涉及文件：`DashboardPage.test.tsx`、`DashboardTwofa.test.tsx`、`AdminPage.test.tsx`。运行这些测试找出顺序断点，逐个补齐；其余用例若 mock 是无差别的 `mockResolvedValue` 则无需改动。

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run src/__tests__/MessagesPage.test.tsx src/__tests__/DashboardPage.test.tsx src/__tests__/DashboardTwofa.test.tsx src/__tests__/AdminPage.test.tsx && npm run lint && npx tsc -b`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/MessagesPage.tsx frontend/src/components/MessageBell.tsx frontend/src/components/bits/LineIcon.tsx frontend/src/components/AppHeader.tsx frontend/src/App.tsx frontend/src/__tests__/MessagesPage.test.tsx frontend/src/__tests__/DashboardPage.test.tsx frontend/src/__tests__/DashboardTwofa.test.tsx frontend/src/__tests__/AdminPage.test.tsx
git commit -m "feat: 用户站内信收件箱与头部未读铃铛"
```

---

### Task 13: 用户中心邮件通知开关

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Test: `frontend/src/__tests__/DashboardPage.test.tsx`

**Interfaces:**
- Consumes: Task 10 `UserOut.email_notifications`、Task 12 的测试序列更新。
- Produces: 基本资料卡新增「接收邮件通知」复选框，随资料保存提交 `email_notifications`。

- [ ] **Step 1: 写失败测试**

在 `DashboardPage.test.tsx` 追加：

```tsx
it("保存资料时提交邮件通知开关", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ unread: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "1",
          email: "a@example.com",
          nickname: "Alice",
          email_verified: true,
          email_notifications: true,
          phone: null,
          role: "user",
          status: "active",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          email_otp_enabled: false,
          totp_enabled: false,
          recovery_codes_remaining: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "1",
          email: "a@example.com",
          nickname: "Alice",
          email_verified: true,
          email_notifications: false,
          phone: null,
          role: "user",
          status: "active",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<DashboardPage />);

  await waitFor(() =>
    expect(screen.getByRole("checkbox", { name: "接收邮件通知" })).toBeChecked()
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "接收邮件通知" }));
  fireEvent.click(screen.getByRole("button", { name: /保存资料/ }));
  await waitFor(() => {
    const put = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/v1/me") && init?.method === "PUT"
    );
    expect(put).toBeDefined();
    const body = JSON.parse(String((put as [unknown, RequestInit])[1].body));
    expect(body.email_notifications).toBe(false);
  });
});
```

（保存按钮的准确可访问名称以现有测试为准，可能是「保存」。）

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run src/__tests__/DashboardPage.test.tsx -t "邮件通知"`
Expected: FAIL（找不到复选框）。

- [ ] **Step 3: 实现**

`DashboardPage.tsx`：

1. 状态：`const [emailNotifications, setEmailNotifications] = useState(true);`（在 `setUser` 成功回调里同步 `setEmailNotifications(data.email_notifications)`；`saveProfileAction` 成功回调里 `setEmailNotifications(updated.email_notifications)`）。
2. `saveProfileAction` 签名改为 `(nickname: string, avatarUrl: string, emailNotifications: boolean)`，payload 加 `email_notifications: emailNotifications`。
3. `saveProfile` 改为 `await saveProfileAction.run(nickname, avatarUrl, emailNotifications);`。
4. 基本资料卡昵称输入附近加：

```tsx
<label className="flex items-center gap-2 text-sm text-foreground">
  <input
    type="checkbox"
    checked={emailNotifications}
    onChange={(e) => setEmailNotifications(e.target.checked)}
    aria-label="接收邮件通知"
  />
  接收邮件通知（关闭后仍会收到站内信）
</label>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run src/__tests__/DashboardPage.test.tsx && npm run lint && npx tsc -b`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/__tests__/DashboardPage.test.tsx
git commit -m "feat: 用户中心邮件通知开关"
```

---

### Task 14: 文档与全量验证

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-14-notifications-design.md`（状态改为“已实施完成”）

- [ ] **Step 1: 更新 CHANGELOG**

在「行为变更」追加一条：

```markdown
- 新增站内信与自定义邮件通知：管理后台「通知管理」可向全部/指定用户发送站内信与邮件（正文支持 `{nickname}`、`{email}` 占位符）；用户中心新增收件箱与头部未读铃铛，并可在资料中关闭邮件通知。设计见 [站内信与自定义邮件通知设计](docs/superpowers/specs/2026-08-14-notifications-design.md)。
```

- [ ] **Step 2: 更新 README**

功能清单「管理后台」与「用户中心」相应位置补：管理后台通知管理（站内信/自定义邮件）、用户中心站内信收件箱与邮件通知开关。

- [ ] **Step 3: spec 状态更新**

`- 状态：设计已确认，待实施` 改为 `- 状态：已实施完成（2026-08-14）`。

- [ ] **Step 4: 全量验证**

```bash
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && npm test && npm run lint && npx tsc -b && npm run build
```

Expected: 后端与前端全部 PASS。

- [ ] **Step 5: 布局冒烟**

用无头 Chrome 在 1280 与 390 宽度打开 `/admin/notifications` 与 `/messages` 预览（stub 接口数据，方法同此前会话面板验证），确认：桌面无横向溢出、表头/徽章单行、移动端整表横滑、铃铛徽章正常显示。

- [ ] **Step 6: 提交**

```bash
git add CHANGELOG.md README.md docs/superpowers/specs/2026-08-14-notifications-design.md
git commit -m "docs: 通知功能发布说明与设计状态"
```

---

## Self-Review

- Spec 覆盖：数据模型（Task 2）、配置（Task 1）、邮件服务（Task 3）、发送/历史接口（Task 4/5）、用户消息接口（Task 6）、偏好（Task 7）、清理（Task 8）、审计分类（Task 4/9）、前端面板/收件箱/铃铛/开关（Task 11/12/13）、文档（Task 14）。全部需求均有对应任务。
- 占位符扫描：无 TBD/TODO；每个代码步骤均给出具体实现。
- 类型一致性：`send_custom_notification_batch` 的 `items` 三元组、`NotificationRecipient` 字段、`MessageListOut.unread`、`UserOut.email_notifications` 在前后端任务间保持一致。

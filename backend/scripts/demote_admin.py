"""把管理员降级为普通用户（与 make_admin 对称的运维脚本）。

安全护栏：拒绝降级最后一名管理员，避免管理员账号被清空后失去后台入口。
"""

import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.user import User, UserRole


def _demote(db, email: str) -> None:
    normalized = email.lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        print(f"用户不存在: {email}")
        sys.exit(1)
    if user.role != UserRole.admin:
        print(f"{email} 已是普通用户，无需降级")
        return
    admin_count = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin)
        # PostgreSQL 下锁住管理员行，避免两个并发降级同时通过“最后一名”校验；
        # SQLite 忽略 FOR UPDATE，测试不受影响。
        .with_for_update()
    )
    if admin_count is not None and admin_count <= 1:
        print("拒绝降级：这是最后一名管理员，请先提升其他管理员")
        sys.exit(1)
    user.role = UserRole.user
    db.commit()
    print(f"已将 {email} 降级为普通用户")


def main(email: str, db=None) -> None:
    """降级入口；db 参数供测试注入会话，缺省使用 SessionLocal。"""
    if db is not None:
        _demote(db, email)
        return
    with SessionLocal() as session:
        _demote(session, email)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python -m scripts.demote_admin <email>")
        sys.exit(2)
    main(sys.argv[1])

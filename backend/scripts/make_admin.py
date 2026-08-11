import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.user import User, UserRole


def main(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            print(f"用户不存在: {email}")
            sys.exit(1)
        user.role = UserRole.admin
        db.commit()
        print(f"已将 {email} 设为管理员")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python -m scripts.make_admin <email>")
        sys.exit(2)
    main(sys.argv[1])

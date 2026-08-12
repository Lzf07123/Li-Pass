from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User

AVATAR_PREFIX = "/uploads/avatars/"


def local_avatar_path(upload_dir: Path, avatar_url: str | None) -> Path | None:
    """把头像 URL 安全解析为本地文件路径；越界路径一律返回 None。"""
    if not avatar_url or not avatar_url.startswith(AVATAR_PREFIX):
        return None
    root = upload_dir.resolve()
    candidate = (root / avatar_url.removeprefix(AVATAR_PREFIX)).resolve()
    if not candidate.is_relative_to(root):
        return None
    return candidate


def delete_avatar_file(
    upload_dir: Path,
    avatar_url: str | None,
    owner_dir: Path | None = None,
) -> bool:
    """删除头像文件。

    owner_dir 非空时只允许删除该目录内的文件，防止跨用户误删。
    """
    path = local_avatar_path(upload_dir, avatar_url)
    if path is None or not path.is_file():
        return False
    if owner_dir is not None and not path.is_relative_to(owner_dir.resolve()):
        return False
    path.unlink(missing_ok=True)
    return True


def cleanup_orphan_avatars(db: Session) -> tuple[int, int]:
    """删除 uploads/avatars 下未被任何用户引用的头像文件，并移除空目录。

    返回 (删除文件数, 删除目录数)，供日志与测试使用。
    """
    upload_dir = Path(get_settings().avatar_upload_dir).resolve()
    if not upload_dir.is_dir():
        return 0, 0

    rows = db.execute(
        select(User.avatar_url).where(User.avatar_url.is_not(None))
    ).all()
    referenced = {
        path.resolve()
        for (url,) in rows
        if (path := local_avatar_path(upload_dir, url)) is not None
    }

    removed_files = 0
    for path in upload_dir.rglob("*"):
        if path.is_file() and path.resolve() not in referenced:
            try:
                path.unlink(missing_ok=True)
                removed_files += 1
            except OSError:
                continue

    removed_dirs = 0
    # 最深目录优先，便于逐层清空。
    for path in sorted(
        upload_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True
    ):
        if path.is_dir():
            try:
                path.rmdir()
                removed_dirs += 1
            except OSError:
                continue

    return removed_files, removed_dirs

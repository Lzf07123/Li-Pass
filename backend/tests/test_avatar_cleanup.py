import uuid
from pathlib import Path

from app.core.config import get_settings
from app.models.user import User
from app.services.avatar_cleanup import cleanup_orphan_avatars, delete_avatar_file
from tests.helpers import register_and_login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _avatar_path(avatar_url: str) -> Path:
    return Path(get_settings().avatar_upload_dir) / avatar_url.removeprefix(
        "/uploads/avatars/"
    )


def test_update_profile_to_external_url_removes_old_file(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    avatar_url = client.post(
        "/api/v1/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
    ).json()["avatar_url"]
    old_path = _avatar_path(avatar_url)
    assert old_path.is_file()

    response = client.put(
        "/api/v1/me", json={"avatar_url": "https://cdn.example.com/a.png"}
    )
    assert response.status_code == 200
    assert not old_path.exists()


def test_update_profile_to_other_local_path_removes_old_file(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    first = client.post(
        "/api/v1/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
    ).json()["avatar_url"]
    first_path = _avatar_path(first)
    assert first_path.is_file()

    # 构造当前用户目录下的另一个合法本地头像地址。
    second = f"/uploads/avatars/{first.split('/')[3]}/{uuid.uuid4().hex}.png"
    second_path = _avatar_path(second)
    second_path.parent.mkdir(parents=True, exist_ok=True)
    second_path.write_bytes(PNG)

    response = client.put("/api/v1/me", json={"avatar_url": second})
    assert response.status_code == 200
    assert not first_path.exists()
    assert second_path.is_file()


def test_cleanup_orphan_avatars_keeps_referenced(db_session) -> None:
    upload_dir = Path(get_settings().avatar_upload_dir)
    uid = uuid.uuid4()
    user_dir = upload_dir / str(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    referenced_name = "a" * 32 + ".png"
    orphan_name = "b" * 32 + ".jpg"
    (user_dir / referenced_name).write_bytes(PNG)
    (user_dir / orphan_name).write_bytes(PNG)
    empty_dir = upload_dir / uuid.uuid4().hex
    empty_dir.mkdir(parents=True, exist_ok=True)

    db_session.add(
        User(
            email=f"{uid}@example.com",
            password_hash="x",
            nickname="Avatar",
            avatar_url=f"/uploads/avatars/{uid}/{referenced_name}",
        )
    )
    db_session.commit()

    removed_files, removed_dirs = cleanup_orphan_avatars(db_session)

    assert (user_dir / referenced_name).is_file()
    assert not (user_dir / orphan_name).exists()
    assert removed_files >= 1
    assert not empty_dir.exists()
    assert removed_dirs >= 1


def test_delete_avatar_file_scoped_to_owner_dir(db_session) -> None:
    upload_dir = Path(get_settings().avatar_upload_dir)
    own = upload_dir / "11111111-1111-1111-1111-111111111111"
    victim = upload_dir / "22222222-2222-2222-2222-222222222222"
    own.mkdir(parents=True, exist_ok=True)
    victim.mkdir(parents=True, exist_ok=True)
    own_file = own / ("c" * 32 + ".png")
    victim_file = victim / ("d" * 32 + ".png")
    own_file.write_bytes(PNG)
    victim_file.write_bytes(PNG)

    assert (
        delete_avatar_file(
            upload_dir,
            f"/uploads/avatars/{victim.name}/{victim_file.name}",
            owner_dir=own,
        )
        is False
    )
    assert victim_file.exists()

    assert (
        delete_avatar_file(
            upload_dir,
            f"/uploads/avatars/{own.name}/{own_file.name}",
            owner_dir=own,
        )
        is True
    )
    assert not own_file.exists()

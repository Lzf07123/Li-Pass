import hashlib
import shutil
from pathlib import Path

import pytest

from app.services.ip2region_pins import BINDING_SHA256, PINNED_SHA256

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_binding_pins_match_vendored_files():
    """信任清单必须与本地 vendored 绑定源码一致，防止镜像/本地行为漂移。"""
    assert len(BINDING_SHA256) == 4
    assert len(PINNED_SHA256) == 2
    for (tag, subpath), expected in BINDING_SHA256.items():
        assert tag == "v3.17.0"
        path = BACKEND_DIR / "ip2region" / Path(subpath).name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected, f"{subpath} 哈希与信任清单不一致"


def _mirror_tree(tmp_path: Path, tamper: bool = False) -> Path:
    """按 {tag}/binding/python/... 结构复制 vendored 文件，模拟镜像。"""
    root = tmp_path / "mirror" / "v3.17.0" / "binding" / "python"
    package = root / "ip2region"
    package.mkdir(parents=True)
    for name in ("__init__.py", "util.py", "searcher.py"):
        content = (BACKEND_DIR / "ip2region" / name).read_bytes()
        if tamper and name == "searcher.py":
            content = b"tampered"
        (package / name).write_bytes(content)
    shutil.copy(BACKEND_DIR / "ip2region" / "LICENSE", root / "LICENSE")
    return tmp_path / "mirror"


def test_fetch_binding_files_downloads_and_verifies(tmp_path):
    from scripts.download_ip2region import _fetch_binding_files

    mirror = _mirror_tree(tmp_path)
    out = tmp_path / "out"
    _fetch_binding_files(mirror.as_uri(), "v3.17.0", out)

    assert (out / "searcher.py").read_bytes() == (
        BACKEND_DIR / "ip2region" / "searcher.py"
    ).read_bytes()
    assert (out / "util.py").read_bytes() == (
        BACKEND_DIR / "ip2region" / "util.py"
    ).read_bytes()
    assert (out / "__init__.py").exists()
    assert (out / "LICENSE").exists()


def test_fetch_binding_files_rejects_tampered_content(tmp_path):
    from scripts.download_ip2region import _fetch_binding_files

    mirror = _mirror_tree(tmp_path, tamper=True)
    with pytest.raises(SystemExit, match="SHA256"):
        _fetch_binding_files(mirror.as_uri(), "v3.17.0", tmp_path / "out")


def test_fetch_binding_files_rejects_unknown_version(tmp_path):
    from scripts.download_ip2region import _fetch_binding_files

    mirror = _mirror_tree(tmp_path)
    with pytest.raises(SystemExit, match="信任清单"):
        _fetch_binding_files(mirror.as_uri(), "v9.9.9", tmp_path / "out")

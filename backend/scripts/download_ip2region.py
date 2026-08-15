#!/usr/bin/env python3
"""下载固定 tag 的 ip2region xdb 数据与 Python 绑定源码（SHA256 校验）。"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ip2region_pins import BINDING_SHA256, PINNED_SHA256

DEFAULT_TAG = "v3.17.0"
DEFAULT_BASE = "https://raw.githubusercontent.com/lionsoul2014/ip2region"


def _download_and_verify(
    url: str, temp: Path, target: Path, expected: str | None, label: str
) -> None:
    """下载单个文件并校验 SHA256；失败即退出，不留下半成品。"""
    print(f"下载 {url}", file=sys.stderr)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Li&Pass/1.0)"},
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, open(
                temp, "wb"
            ) as out:
                shutil.copyfileobj(response, out)
            break
        except (URLError, HTTPError, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    else:
        raise last_error
    digest = hashlib.sha256(temp.read_bytes()).hexdigest()
    if expected is None:
        temp.unlink()
        raise SystemExit(f"{label} 未列入信任清单，请先在 ip2region_pins.py 中固定哈希")
    if digest != expected:
        temp.unlink()
        raise SystemExit(f"SHA256 校验失败：{label}（{digest}）")
    os.replace(temp, target)


def _fetch_binding_files(base_url: str, tag: str, binding_dir: Path) -> None:
    """从固定 tag 拉取 Python 绑定源码（含 LICENSE），逐文件校验哈希。"""
    binding_dir.mkdir(parents=True, exist_ok=True)
    for subpath in (
        "ip2region/__init__.py",
        "ip2region/util.py",
        "ip2region/searcher.py",
        "LICENSE",
    ):
        expected = BINDING_SHA256.get((tag, subpath))
        if expected is None:
            raise SystemExit(
                f"绑定文件 {subpath} 未列入信任清单，"
                "请先在 ip2region_pins.py 中固定哈希"
            )
        url = f"{base_url.rstrip('/')}/{tag}/binding/python/{subpath}"
        # binding_dir 即 ip2region 包目录：源码平铺写入（含 LICENSE），
        # 使 `<parent>/ip2region/` 可直接作为顶层包导入。
        target = binding_dir / (subpath if subpath == "LICENSE" else Path(subpath).name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        _download_and_verify(url, temp, target, expected, subpath)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--data-dir", default="data/ip2region")
    parser.add_argument(
        "--binding-dir",
        default=None,
        help="同时拉取 Python 绑定源码到该目录（用于更新仓库入库的 vendored 目录）",
    )
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("ip2region_v4.xdb", "ip2region_v6.xdb"):
        expected = PINNED_SHA256.get((args.tag, filename))
        if expected is None:
            raise SystemExit(
                f"版本 {args.tag} 未列入信任清单，"
                "请先在 ip2region_pins.py 中固定哈希"
            )
        url = f"{args.base_url.rstrip('/')}/{args.tag}/data/{filename}"
        _download_and_verify(
            url, data_dir / f"{filename}.tmp", data_dir / filename, expected, filename
        )
    if args.binding_dir:
        _fetch_binding_files(args.base_url.rstrip("/"), args.tag, Path(args.binding_dir))
    meta = {
        "version": args.tag,
        "data_updated_at": None,
        "last_check_at": None,
    }
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"完成：{data_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

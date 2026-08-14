#!/usr/bin/env python3
"""下载固定 tag 的 ip2region xdb 数据并写 meta.json（SHA256 校验）。"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ip2region_pins import PINNED_SHA256

DEFAULT_TAG = "v3.17.0"
DEFAULT_BASE = "https://raw.githubusercontent.com/lionsoul2014/ip2region"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--data-dir", default="data/ip2region")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("ip2region_v4.xdb", "ip2region_v6.xdb"):
        url = f"{args.base_url.rstrip('/')}/{args.tag}/data/{filename}"
        temp = data_dir / f"{filename}.tmp"
        print(f"下载 {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=60) as response, open(
            temp, "wb"
        ) as out:
            shutil.copyfileobj(response, out)
        digest = hashlib.sha256(temp.read_bytes()).hexdigest()
        expected = PINNED_SHA256.get((args.tag, filename))
        if expected is None:
            temp.unlink()
            raise SystemExit(f"版本 {args.tag} 未列入信任清单，请先在 ip2region_pins.py 中固定哈希")
        if digest != expected:
            temp.unlink()
            raise SystemExit(f"SHA256 校验失败：{filename}（{digest}）")
        os.replace(temp, data_dir / filename)
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

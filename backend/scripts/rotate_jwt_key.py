"""生成下一把 JWT 签名密钥（目录模式），并打印滚动发布步骤。

用法（backend 目录下）: python -m scripts.rotate_jwt_key

前提：
1. 已配置 JWT_KEYS_DIR（如 /app/keys/jwt），目录中每个 *.pem 的文件名即 kid；
2. 迁移单文件模式时，把原 jwt_private.pem 重命名为 lipass-rs256-1.pem
   放入该目录，保证旧 token 的 kid 继续可验证。

脚本只生成新密钥、不修改运行态；按打印的步骤滚动更新 JWT_ACTIVE_KID 并重启，
JWKS 会同时发布目录内全部公钥，旧 token 在密钥删除前始终可验证。
"""

import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.security.crypto import atomic_write_bytes

KID_PATTERN = re.compile(r"^lipass-rs256-(\d+)\.pem$")
# 品牌改名前的历史文件（portal-rs256-*.pem）继续参与编号，避免新密钥
# 与其撞号；旧文件可继续用其文件名作 kid 验证历史 token。
LEGACY_KID_PATTERN = re.compile(r"^portal-rs256-(\d+)\.pem$")


def next_kid(keys_dir: Path) -> str:
    """在现有 lipass-rs256-*/portal-rs256-* 文件之上取下一个连续编号。"""
    existing: list[int] = []
    for pem in keys_dir.glob("*.pem"):
        for pattern in (KID_PATTERN, LEGACY_KID_PATTERN):
            match = pattern.match(pem.name)
            if match is not None:
                existing.append(int(match.group(1)))
                break
    return f"lipass-rs256-{max(existing, default=1) + 1}"


def main() -> int:
    settings = get_settings()
    if not settings.jwt_keys_dir:
        print("未配置 JWT_KEYS_DIR，无法生成轮换密钥。", file=sys.stderr)
        print(
            "请先设置 JWT_KEYS_DIR（如 /app/keys/jwt），并把现有 "
            "jwt_private.pem 重命名为 lipass-rs256-1.pem 放入该目录后重试。",
            file=sys.stderr,
        )
        return 1

    keys_dir = Path(settings.jwt_keys_dir)
    keys_dir.mkdir(parents=True, exist_ok=True)
    kid = next_kid(keys_dir)
    target = keys_dir / f"{kid}.pem"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    atomic_write_bytes(
        target,
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )

    print(f"已生成新密钥: {target}")
    print()
    print("滚动发布步骤：")
    print(f"1. 设置环境变量 JWT_ACTIVE_KID={kid}")
    print("2. 滚动重启 backend：新进程用新 kid 签名，JWKS 同时发布目录内全部公钥")
    print("3. 等待超过 access token 最长有效期（15 分钟，建议 1 小时）")
    print("4. 删除目录内旧 *.pem 文件（JWT_ACTIVE_KID 必须仍指向存在的密钥）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

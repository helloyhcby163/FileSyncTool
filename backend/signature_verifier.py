# -*- coding: utf-8 -*-
"""v7.8.0 - 更新包签名校验（Ed25519 占位实现）。

开发阶段 PUBLIC_KEY 为空时默认放行并打印警告；
正式发布前填入 Ed25519 公钥（64 位十六进制或 base64 原始 32 字节，或 PEM），
即可启用严格的 Ed25519 验签。
"""

import base64
import binascii
from pathlib import Path

# 占位公钥：为空表示尚未接入正式签名，开发阶段全部放行。
# 支持格式：
# 1) 64 个十六进制字符
# 2) base64 编码的 32 字节原始公钥
# 3) PEM（-----BEGIN PUBLIC KEY-----）
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAXFMpbjef1qRII5jmCcvupp8aXA2knIkOfYQgbIzv9X8=
-----END PUBLIC KEY-----"""

# 默认签名文件后缀（例如 update.zip.sig）
SIGNATURE_SUFFIX = ".sig"


def _decode_public_key(value: str):
    """把 PUBLIC_KEY 字符串解码为 Ed25519 公钥对象。"""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    text = str(value or "").strip()
    if "BEGIN PUBLIC KEY" in text:
        key = load_pem_public_key(text.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("PEM 公钥不是 Ed25519 类型")
        return key

    compact = "".join(text.split())
    if len(compact) == 64:
        try:
            raw = bytes.fromhex(compact)
            return Ed25519PublicKey.from_public_bytes(raw)
        except (ValueError, binascii.Error):
            pass
    raw = base64.b64decode(compact, validate=True)
    return Ed25519PublicKey.from_public_bytes(raw)


def verify_signature(file_path, sig_path=None) -> bool:
    """
    校验 file_path 的 Ed25519 签名。

    Args:
        file_path: 待校验文件路径
        sig_path: 签名文件路径；为 None 时使用 ``<file_path>.sig``

    Returns:
        True 表示校验通过（或开发阶段未配置公钥，默认放行）；
        False 表示验签失败、文件/签名缺失或依赖不可用。
    """
    if not PUBLIC_KEY:
        print(
            "⚠️ 未配置 Ed25519 公钥（PUBLIC_KEY 为空），"
            "开发阶段默认放行签名校验"
        )
        return True

    path = Path(file_path).resolve()
    signature_path = (
        Path(sig_path).resolve()
        if sig_path
        else Path(str(path) + SIGNATURE_SUFFIX).resolve()
    )

    if not path.is_file():
        print(f"⚠️ 验签失败：文件不存在「{path}」")
        return False
    if not signature_path.is_file():
        print(f"⚠️ 验签失败：签名文件不存在「{signature_path}」")
        return False

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except ImportError:
        print("⚠️ 验签失败：未安装 cryptography 依赖")
        return False

    try:
        public_key = _decode_public_key(PUBLIC_KEY)
        if not isinstance(public_key, Ed25519PublicKey):
            print("⚠️ 验签失败：PUBLIC_KEY 不是 Ed25519 公钥")
            return False
        signature = signature_path.read_bytes()
        data = path.read_bytes()
        public_key.verify(signature, data)
        return True
    except InvalidSignature:
        print(f"⚠️ 验签失败：签名不匹配「{path}」")
        return False
    except (OSError, ValueError, TypeError, binascii.Error) as exc:
        print(f"⚠️ 验签失败：{exc}")
        return False

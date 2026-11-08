from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

# 1. 生成私钥（千万不能泄露给任何人！）
private_key = Ed25519PrivateKey.generate()
pem_private = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# 2. 生成公钥（这个打包进软件中）
public_key = private_key.public_key()
pem_public = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print("--- 你的私钥 (保存在本地，用于签名，千万别打包) ---")
print(pem_private.decode())
print("--- 你的公钥 (打包进软件，硬编码在 signature_verifier.py) ---")
print(pem_public.decode())
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretBox:
    """AES-256-GCM，密文格式 v1:{key_id}:{nonce}:{ciphertext}。"""

    def __init__(self, key_b64: str, key_id: str = "k1") -> None:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise ValueError("key must decode to 32 bytes")
        self._aes = AESGCM(key)
        self.key_id = key_id

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self._aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return (
            f"v1:{self.key_id}:"
            f"{base64.b64encode(nonce).decode()}:"
            f"{base64.b64encode(ciphertext).decode()}"
        )

    def decrypt(self, token: str) -> str:
        version, key_id, nonce_b64, ciphertext_b64 = token.split(":", 3)
        if version != "v1":
            raise ValueError(f"unsupported token version: {version}")
        plaintext = self._aes.decrypt(
            base64.b64decode(nonce_b64),
            base64.b64decode(ciphertext_b64),
            None,
        )
        return plaintext.decode("utf-8")

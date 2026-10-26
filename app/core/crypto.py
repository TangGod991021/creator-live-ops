import base64
import binascii
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,20}$")


class InvalidTokenError(ValueError):
    pass


class SecretBox:
    """AES-256-GCM，密文格式 v1:{key_id}:{nonce}:{ciphertext}。"""

    def __init__(self, key_b64: str, key_id: str = "k1") -> None:
        if not _KEY_ID_PATTERN.fullmatch(key_id):
            raise ValueError("key_id must match ^[A-Za-z0-9_-]{1,20}$")
        try:
            key = base64.b64decode(key_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("key must be valid base64") from exc
        if len(key) != 32:
            raise ValueError("key must decode to 32 bytes")
        self._aes = AESGCM(key)
        self.key_id = key_id

    def encrypt(self, plaintext: str, aad: str | None = None) -> str:
        nonce = os.urandom(12)
        associated = aad.encode("utf-8") if aad is not None else None
        ciphertext = self._aes.encrypt(nonce, plaintext.encode("utf-8"), associated)
        return (
            f"v1:{self.key_id}:"
            f"{base64.b64encode(nonce).decode()}:"
            f"{base64.b64encode(ciphertext).decode()}"
        )

    def decrypt(self, token: str, aad: str | None = None) -> str:
        version, key_id, nonce_b64, ciphertext_b64 = self._split(token)
        if version != "v1":
            raise InvalidTokenError(f"unsupported token version: {version}")
        if key_id != self.key_id:
            raise InvalidTokenError("key_id mismatch")
        associated = aad.encode("utf-8") if aad is not None else None
        try:
            nonce = base64.b64decode(nonce_b64, validate=True)
            ciphertext = base64.b64decode(ciphertext_b64, validate=True)
            plaintext = self._aes.decrypt(nonce, ciphertext, associated)
            return plaintext.decode("utf-8")
        except (InvalidTag, binascii.Error, ValueError) as exc:
            raise InvalidTokenError("token authentication failed") from exc

    @staticmethod
    def _split(token: str) -> tuple[str, str, str, str]:
        parts = token.split(":")
        if len(parts) != 4:
            raise InvalidTokenError("invalid token format")
        return parts[0], parts[1], parts[2], parts[3]

    def key_id_of(self, token: str) -> str:
        return self._split(token)[1]

    def needs_reencrypt(self, token: str) -> bool:
        return self.key_id_of(token) != self.key_id

    def reencrypt(self, token: str, to_box: "SecretBox", aad: str | None = None) -> str:
        return to_box.encrypt(self.decrypt(token, aad=aad), aad=aad)

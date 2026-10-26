import base64

import pytest

from app.core.crypto import InvalidTokenError, SecretBox

KEY_B64 = base64.b64encode(b"k" * 32).decode()


def make_box(key_id: str = "k1") -> SecretBox:
    return SecretBox(KEY_B64, key_id=key_id)


def test_roundtrip() -> None:
    box = make_box()
    token = box.encrypt("hello")
    assert token.startswith("v1:k1:")
    assert box.decrypt(token) == "hello"


def test_roundtrip_empty_plaintext() -> None:
    box = make_box()
    assert box.decrypt(box.encrypt("")) == ""


def test_tampered_ciphertext_raises() -> None:
    box = make_box()
    version, key_id, nonce_b64, ciphertext_b64 = box.encrypt("hello").split(":")
    raw = bytearray(base64.b64decode(ciphertext_b64))
    raw[0] ^= 0x01
    tampered = (
        f"{version}:{key_id}:{nonce_b64}:{base64.b64encode(bytes(raw)).decode()}"
    )
    with pytest.raises(InvalidTokenError):
        box.decrypt(tampered)


def test_wrong_key_raises() -> None:
    box = make_box()
    other = SecretBox(base64.b64encode(b"z" * 32).decode())
    with pytest.raises(InvalidTokenError):
        other.decrypt(box.encrypt("hello"))


def test_key_id_mismatch_raises() -> None:
    box = make_box()
    version, _, nonce_b64, ciphertext_b64 = box.encrypt("hello").split(":")
    token = f"{version}:other:{nonce_b64}:{ciphertext_b64}"
    with pytest.raises(InvalidTokenError, match="key_id mismatch"):
        box.decrypt(token)


def test_invalid_key_id_rejected() -> None:
    with pytest.raises(ValueError, match="key_id"):
        SecretBox(KEY_B64, key_id="a:b")


def test_non_base64_key_rejected() -> None:
    with pytest.raises(ValueError, match="valid base64"):
        SecretBox("!!!not-base64!!!")


def test_short_key_rejected() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        SecretBox(base64.b64encode(b"short").decode())


def test_malformed_token_rejected() -> None:
    box = make_box()
    with pytest.raises(InvalidTokenError, match="invalid token format"):
        box.decrypt("v1:k1:onlythree")


def test_unsupported_version_rejected() -> None:
    box = make_box()
    token = box.encrypt("hello")
    _, key_id, nonce_b64, ciphertext_b64 = token.split(":")
    with pytest.raises(InvalidTokenError, match="unsupported token version"):
        box.decrypt(f"v2:{key_id}:{nonce_b64}:{ciphertext_b64}")


def test_aad_roundtrip_and_mismatch() -> None:
    box = make_box()
    token = box.encrypt("hello", aad="ctx")
    assert box.decrypt(token, aad="ctx") == "hello"
    with pytest.raises(InvalidTokenError):
        box.decrypt(token, aad="wrong")


def test_key_id_of_and_needs_reencrypt() -> None:
    box = make_box()
    token = box.encrypt("hello")
    assert box.key_id_of(token) == "k1"
    assert box.needs_reencrypt(token) is False


def test_reencrypt_to_new_box() -> None:
    old_box = make_box()
    new_box = SecretBox(base64.b64encode(b"z" * 32).decode(), key_id="k2")
    rotated = old_box.reencrypt(old_box.encrypt("hello"), new_box)
    assert rotated.startswith("v1:k2:")
    assert new_box.decrypt(rotated) == "hello"

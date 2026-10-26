import base64

import pytest

from app.core.crypto import SecretBox


def make_box() -> SecretBox:
    return SecretBox(base64.b64encode(b"k" * 32).decode(), key_id="k1")


def test_roundtrip() -> None:
    box = make_box()
    token = box.encrypt("hello")
    assert token.startswith("v1:k1:")
    assert box.decrypt(token) == "hello"


def test_tampered_token_raises() -> None:
    box = make_box()
    token = box.encrypt("hello")
    with pytest.raises(Exception):  # noqa: B017 - any failure is acceptable
        box.decrypt(token[:-2] + "AA")


def test_wrong_key_raises() -> None:
    box = make_box()
    other = SecretBox(base64.b64encode(b"z" * 32).decode())
    with pytest.raises(Exception):  # noqa: B017 - any failure is acceptable
        other.decrypt(box.encrypt("hello"))

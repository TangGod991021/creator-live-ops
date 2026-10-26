from app.core.logging import redact


def test_redact_key_value_secret() -> None:
    assert redact("password=abc123 api_key: xyz") == "password=*** api_key=***"


def test_redact_phone() -> None:
    assert redact("phone 13812345678") == "phone 138****5678"


def test_redact_leaves_normal_text() -> None:
    assert redact("gmv=1234.56") == "gmv=1234.56"

import pytest
from loguru import logger

from app.core.logging import redact, setup_logging


def test_redact_key_value_secret() -> None:
    assert redact("password=abc123 api_key: xyz") == "password=*** api_key: ***"


def test_redact_phone() -> None:
    assert redact("phone 13812345678") == "phone 138****5678"


def test_redact_leaves_normal_text() -> None:
    assert redact("gmv=1234.56") == "gmv=1234.56"


def test_redact_json_secret() -> None:
    assert redact('{"password": "abc123", "user": "u"}') == '{"password": "***", "user": "u"}'


def test_redact_quoted_value_with_spaces() -> None:
    assert redact('password="abc def"') == 'password="***"'


def test_redact_authorization_header() -> None:
    assert redact("Authorization: Bearer eyJabc") == "Authorization: ***"


def test_redact_query_string_token() -> None:
    assert redact("?token=abc123&x=1") == "?token=***&x=1"


def test_redact_does_not_touch_max_tokens() -> None:
    assert redact("max_tokens=100") == "max_tokens=100"


def test_setup_logging_redacts_plain_message(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    logger.info("password=abc123 phone 13812345678")
    stderr = capsys.readouterr().err
    assert "abc123" not in stderr
    assert "13812345678" not in stderr


def test_setup_logging_redacts_json_extra(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_logs=True)
    logger.info("login", token="SUPERSECRET", password="abc123")
    stderr = capsys.readouterr().err
    assert "SUPERSECRET" not in stderr
    assert "abc123" not in stderr


def test_setup_logging_redacts_exception_text(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    try:
        raise RuntimeError("password=hunter2 phone 13812345678")
    except RuntimeError:
        logger.exception("boom")
    stderr = capsys.readouterr().err
    assert "hunter2" not in stderr
    assert "13812345678" not in stderr


def test_setup_logging_removes_existing_handlers() -> None:
    received: list[str] = []
    logger.add(received.append)
    setup_logging()
    logger.info("hello")
    assert received == []

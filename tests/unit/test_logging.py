import json

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


def test_redact_composite_key_names() -> None:
    assert (
        redact("db_password=hunter2 oauth_access_token=abc")
        == "db_password=*** oauth_access_token=***"
    )


def test_redact_escaped_quoted_value() -> None:
    assert redact('password=\\"abc def\\"') == 'password=\\"***\\"'


def test_redact_url_credentials() -> None:
    assert redact("mysql://user:pw@host:3306/db") == "mysql://user:***@host:3306/db"


def test_redact_cookie_header() -> None:
    assert redact("Cookie: a=1; b=2") == "Cookie: ***"


def test_redact_phone_with_country_code() -> None:
    assert redact("+8613812345678") == "+86138****5678"


def test_redact_phone_with_hyphens() -> None:
    assert redact("138-1234-5678") == "138****5678"


def test_setup_logging_redacts_and_keeps_plain_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging()
    logger.info("password=abc123 phone 13812345678")
    err = capsys.readouterr().err
    assert "password=***" in err
    assert "138****5678" in err
    assert "abc123" not in err
    assert "13812345678" not in err


def test_setup_logging_json_extra_is_valid_and_redacted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging(json_logs=True)
    logger.info("login", token="SUPERSECRET", password="abc123")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]
    assert records[0]["record"]["extra"]["token"] == "***"
    assert records[0]["record"]["extra"]["password"] == "***"
    assert "SUPERSECRET" not in json.dumps(records[0])
    assert "abc123" not in json.dumps(records[0])


def test_setup_logging_json_output_is_valid_for_secret_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging(json_logs=True)
    logger.info("password=abc123")
    logger.info("Authorization: Bearer SECRET123")
    logger.info("Cookie: sid=SECRET123")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]
    assert len(records) == 3
    assert all("***" in record["text"] for record in records)
    serialized = json.dumps(records)
    assert "abc123" not in serialized
    assert "SECRET123" not in serialized


def test_setup_logging_json_message_payload(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_logs=True)
    logger.info(json.dumps({"password": "abc123", "user": "u"}))
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]
    assert "abc123" not in records[0]["text"]
    assert "***" in records[0]["text"]


def test_setup_logging_redacts_exception(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    try:
        raise RuntimeError("password=hunter2 phone 13812345678")
    except RuntimeError:
        logger.exception("boom")
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "password=***" in err
    assert "hunter2" not in err
    assert "13812345678" not in err


def test_setup_logging_removes_existing_handlers() -> None:
    received: list[str] = []
    logger.add(received.append)
    setup_logging()
    logger.info("hello")
    assert received == []

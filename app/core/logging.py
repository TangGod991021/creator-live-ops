import re
import sys

from loguru import logger

_SECRET_PATTERN = re.compile(
    r"(?i)\b(access[_-]?token|refresh[_-]?token|app[_-]?secret|api[_-]?key|password|secret)"
    r"\s*[=:]\s*([^\s,;&]+)"
)
_PHONE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")


def redact(text: str) -> str:
    text = _SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=***", text)
    return _PHONE_PATTERN.sub(lambda m: f"{m.group(1)[:3]}****{m.group(1)[-4:]}", text)


def setup_logging(json_logs: bool = False) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        serialize=json_logs,
        filter=lambda record: record.update(message=redact(record["message"])) or True,
        level="INFO",
    )

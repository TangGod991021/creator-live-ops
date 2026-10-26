import re
import sys

from loguru import logger

_KEY_NAMES = (
    r"access[_-]?token|refresh[_-]?token|client[_-]?secret|secret[_-]?key|"
    r"app[_-]?secret|api[_-]?key|apikey|authorization|cookie|session[_-]?id|"
    r"sessionid|password|passwd|pwd|secret|token"
)
_SECRET_PATTERN = re.compile(
    rf"""(?ix)
    (?P<prefix>
        ["']?
        (?<![A-Za-z0-9_])
        (?:{_KEY_NAMES})
        (?![A-Za-z0-9_])
        ["']?
        \s*[:=]\s*
    )
    (?P<value>
        "[^"]*" |
        '[^']*' |
        [^\s,;&}}]+
    )
    """
)
_AUTH_PATTERN = re.compile(
    r"(?i)(?P<prefix>\bauthorization\s*[:=]\s*)(?P<value>[^\r\n,;&}]+)"
)
_PHONE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")


def _mask_value(match: re.Match[str]) -> str:
    value = match.group("value")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        masked = f"{value[0]}***{value[0]}"
    else:
        masked = "***"
    return f"{match.group('prefix')}{masked}"


def redact(text: str) -> str:
    text = _AUTH_PATTERN.sub(lambda m: f"{m.group('prefix')}***", text)
    text = _SECRET_PATTERN.sub(_mask_value, text)
    return _PHONE_PATTERN.sub(lambda m: f"{m.group(0)[:3]}****{m.group(0)[-4:]}", text)


def _redact_sink(message: str) -> None:
    sys.stderr.write(redact(message))
    sys.stderr.flush()


def setup_logging(json_logs: bool = False, level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        _redact_sink,
        serialize=json_logs,
        level=level,
        backtrace=False,
        diagnose=False,
    )

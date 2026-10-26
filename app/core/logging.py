import re
import sys

from loguru import logger

_KEY_NAMES = (
    r"aws[_-]?secret[_-]?access[_-]?key|secret[_-]?access[_-]?key|"
    r"oauth[_-]?access[_-]?token|database[_-]?password|db[_-]?password|"
    r"encryption[_-]?key|private[_-]?key|signing[_-]?key|webhook[_-]?secret|"
    r"access[_-]?token|refresh[_-]?token|client[_-]?secret|secret[_-]?key|"
    r"app[_-]?secret|api[_-]?key|apikey|authorization|cookie|session[_-]?id|"
    r"sessionid|csrf[_-]?token|id[_-]?token|auth[_-]?token|x[_-]?api[_-]?key|"
    r"password|passwd|pwd|secret|token"
)
_SECRET_PATTERN = re.compile(
    rf"""(?ix)
    (?P<prefix>
        (?:\\?["'])?
        (?<![A-Za-z0-9_])
        (?:{_KEY_NAMES})
        (?![A-Za-z0-9_])
        (?:\\?["'])?
        \s*[:=]\s*
    )
    (?P<value>
        \\"[^"\\]*\\" |
        "[^"]*" |
        '[^']*' |
        [^\s,;&"\\}}]+
    )
    """
)
_AUTH_PATTERN = re.compile(
    r"(?i)(?P<prefix>\bauthorization\s*[:=]\s*)(?P<value>[^\r\n,;&\"\\}]+)"
)
_COOKIE_PATTERN = re.compile(
    r"(?i)(?P<prefix>\bcookie\s*[:=]\s*)(?P<value>[^\r\n\"\\]+)"
)
_URL_CRED_PATTERN = re.compile(r"(?P<prefix>://[^:/\s]+:)(?P<value>[^@\s]+)(?P<suffix>@)")
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?P<prefix>\+?86[- ]?)?(?P<core>1[3-9]\d(?:[- ]?\d{4}){2})(?!\d)"
)


def _mask_value(match: re.Match[str]) -> str:
    value = match.group("value")
    if value.startswith('\\"') and value.endswith('\\"'):
        masked = '\\"***\\"'
    elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        masked = f"{value[0]}***{value[0]}"
    else:
        masked = "***"
    return f"{match.group('prefix')}{masked}"


def _mask_phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group("core"))
    masked = f"{digits[:3]}****{digits[-4:]}"
    return f"{match.group('prefix') or ''}{masked}"


def redact(text: str) -> str:
    text = _AUTH_PATTERN.sub(lambda m: f"{m.group('prefix')}***", text)
    text = _COOKIE_PATTERN.sub(lambda m: f"{m.group('prefix')}***", text)
    text = _URL_CRED_PATTERN.sub(
        lambda m: f"{m.group('prefix')}***{m.group('suffix')}", text
    )
    text = _SECRET_PATTERN.sub(_mask_value, text)
    return _PHONE_PATTERN.sub(_mask_phone, text)


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

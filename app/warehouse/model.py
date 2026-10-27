from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SqlModel:
    layer: str
    target: str
    depends_on: tuple[str, ...]
    incremental_key: str | None
    window: str
    sql: str
    path: Path

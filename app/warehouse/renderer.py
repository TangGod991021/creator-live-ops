from dataclasses import dataclass
from datetime import datetime

from jinja2 import Environment, StrictUndefined

LAYERS = ("ods", "dim", "dwd", "dws", "ads")

_ENV = Environment(undefined=StrictUndefined, autoescape=False)


def split_layer(table: str) -> tuple[str | None, str]:
    for layer in LAYERS:
        prefix = f"{layer}_"
        if table.startswith(prefix):
            return layer, table[len(prefix) :]
    return None, table


@dataclass(frozen=True)
class TableRenderer:
    layout: str

    def ref(self, logical_name: str) -> str:
        layer, stem = split_layer(logical_name)
        if layer is None or self.layout == "single_db":
            return logical_name
        return f"{layer}.{stem}"


def render_sql(
    sql: str,
    renderer: TableRenderer,
    start_at: datetime,
    end_at: datetime,
) -> str:
    template = _ENV.from_string(sql)
    return template.render(
        ref=renderer.ref,
        start_at=start_at.strftime("%Y-%m-%d %H:%M:%S"),
        end_at=end_at.strftime("%Y-%m-%d %H:%M:%S"),
    )

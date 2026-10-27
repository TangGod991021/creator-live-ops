from datetime import datetime

import pytest
from jinja2 import UndefinedError

from app.warehouse.renderer import TableRenderer, render_sql


def test_single_db_ref_is_identity() -> None:
    renderer = TableRenderer(layout="single_db")
    assert renderer.ref("dwd_order") == "dwd_order"


def test_multi_schema_ref_splits_layer() -> None:
    renderer = TableRenderer(layout="multi_schema")
    assert renderer.ref("dwd_order") == "dwd.order"
    assert renderer.ref("ads_talent_daily") == "ads.talent_daily"


def test_unknown_prefix_is_identity() -> None:
    renderer = TableRenderer(layout="multi_schema")
    assert renderer.ref("sys_config") == "sys_config"


def test_render_ref_and_window() -> None:
    renderer = TableRenderer(layout="single_db")
    sql = "SELECT * FROM {{ ref('dwd_order') }} WHERE pay_at >= '{{ start_at }}'"
    rendered = render_sql(
        sql,
        renderer,
        start_at=datetime(2026, 10, 25),
        end_at=datetime(2026, 10, 26),
    )
    assert "FROM dwd_order" in rendered
    assert "2026-10-25 00:00:00" in rendered


def test_unknown_variable_raises() -> None:
    renderer = TableRenderer(layout="single_db")
    with pytest.raises(UndefinedError):
        render_sql(
            "SELECT '{{ missing }}'",
            renderer,
            start_at=datetime(2026, 10, 25),
            end_at=datetime(2026, 10, 26),
        )

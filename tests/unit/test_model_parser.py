from pathlib import Path

import pytest

from app.warehouse.parser import ModelParseError, parse_model


def write_model(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_header(tmp_path: Path) -> None:
    path = write_model(
        tmp_path,
        "200_dws.sql",
        """-- @layer: dws
-- @target: dws_demo_talent_daily
-- @depends_on: dwd_demo_order
-- @incremental_key: stat_date
-- @window: day

SELECT 1;
""",
    )
    model = parse_model(path)
    assert model.layer == "dws"
    assert model.target == "dws_demo_talent_daily"
    assert model.depends_on == ("dwd_demo_order",)
    assert model.incremental_key == "stat_date"
    assert model.window == "day"
    assert "SELECT 1;" in model.sql


def test_missing_layer_rejected(tmp_path: Path) -> None:
    path = write_model(
        tmp_path,
        "bad.sql",
        """-- @target: bad
-- @depends_on:
""",
    )
    with pytest.raises(ModelParseError, match="missing layer"):
        parse_model(path)

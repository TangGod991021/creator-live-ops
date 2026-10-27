from pathlib import Path

import pytest
import yaml

from app.adapters.csv.mapping import CsvMappingError, load_mapping, load_mappings


def write_mapping(tmp_path: Path, body: dict) -> Path:
    path = tmp_path / "orders.yml"
    path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
    return path


def valid_body() -> dict:
    return {
        "dataset": "orders",
        "resource": "orders",
        "target_table": "ods_order",
        "encoding": "utf-8-sig",
        "delimiter": ",",
        "window_column": "pay_at",
        "key_columns": ["order_id"],
        "required": ["order_id"],
        "datetime_columns": ["pay_at"],
        "decimal_columns": ["pay_amount"],
        "on_error": "skip",
        "fields": {
            "order_id": "order_id",
            "pay_at": "pay_at",
            "pay_amount": "pay_amount",
        },
    }


def test_load_mapping(tmp_path: Path) -> None:
    mapping = load_mapping(write_mapping(tmp_path, valid_body()))
    assert mapping.dataset == "orders"
    assert mapping.window_column == "pay_at"
    assert mapping.fields["pay_amount"] == "pay_amount"


def test_load_mapping_rejects_unknown_on_error(tmp_path: Path) -> None:
    body = valid_body()
    body["on_error"] = "ignore"
    with pytest.raises(CsvMappingError, match="on_error"):
        load_mapping(write_mapping(tmp_path, body))


def test_load_mapping_rejects_unmapped_datetime_column(tmp_path: Path) -> None:
    body = valid_body()
    body["datetime_columns"] = ["missing"]
    with pytest.raises(CsvMappingError, match="datetime_columns"):
        load_mapping(write_mapping(tmp_path, body))


def test_default_mappings_cover_four_datasets() -> None:
    mappings = load_mappings(Path("app/adapters/csv/mappings"))
    assert set(mappings) == {"orders", "after_sales", "settlements", "live_rooms"}

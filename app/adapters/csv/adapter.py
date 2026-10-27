import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.adapters.csv.mapping import CsvMapping, load_mappings
from app.adapters.values import parse_datetime, parse_decimal


class CsvImportError(PermanentError):
    pass


class CsvImportAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, csv_dir: str | Path, mappings_dir: str | Path) -> None:
        self._csv_dir = Path(csv_dir)
        self._mappings = load_mappings(Path(mappings_dir))
        self.errors: list[str] = []

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("orders", window)

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("after_sales", window)

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("settlements", window)

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("live_rooms", window)

    def _fetch(self, resource: str, window: TimeWindow) -> list[dict[str, Any]]:
        self.errors = []
        mapping = self._mappings.get(resource)
        if mapping is None:
            raise PermanentError(f"csv mapping not found for {resource}")
        files = sorted((self._csv_dir / mapping.dataset).glob("*.csv"))
        if not files:
            return []
        records: dict[tuple[str, ...], dict[str, Any]] = {}
        for path in files:
            for row in self._read_file(path, mapping, window):
                key = tuple(str(row[column]) for column in mapping.key_columns)
                records[key] = row
        return list(records.values())

    def _read_file(
        self, path: Path, mapping: CsvMapping, window: TimeWindow
    ) -> list[dict[str, Any]]:
        text = self._read_text(path, mapping.encoding)
        reader = csv.DictReader(io.StringIO(text), delimiter=mapping.delimiter)
        rows: list[dict[str, Any]] = []
        for line_no, source_row in enumerate(reader, start=2):
            normalized_row = {
                (key or "").strip().lstrip("﻿"): (value or "").strip()
                for key, value in source_row.items()
                if key is not None
            }
            try:
                row = self._convert_row(normalized_row, mapping, source_row)
                if row is None:
                    continue
                if mapping.window_column and not _in_window(
                    row.get(mapping.window_column), window
                ):
                    continue
                rows.append(row)
            except CsvImportError as exc:
                message = f"{path}:{line_no}: {exc}"
                if mapping.on_error == "raise":
                    raise CsvImportError(message) from exc
                self.errors.append(message)
        return rows

    def _convert_row(
        self,
        row: dict[str, str],
        mapping: CsvMapping,
        source_row: dict[str, str],
    ) -> dict[str, Any] | None:
        if not any(row.values()):
            return None
        converted: dict[str, Any] = {}
        for source_header, target in mapping.fields.items():
            if source_header not in row:
                continue
            value: Any = row[source_header]
            if target in mapping.datetime_columns:
                value = parse_datetime(value)
            elif target in mapping.decimal_columns:
                value = parse_decimal(value)
            converted[target] = value
        for column in mapping.required:
            value = converted.get(column)
            if value is None or value == "":
                raise CsvImportError(f"required column {column} is empty")
        for column in mapping.datetime_columns:
            if column in converted and converted[column] is None:
                raise CsvImportError(f"datetime column {column} is invalid")
        for column in mapping.decimal_columns:
            if column in converted and converted[column] is None:
                raise CsvImportError(f"decimal column {column} is invalid")
        converted["raw_json"] = {
            str(key): value for key, value in source_row.items() if key is not None
        }
        return converted

    @staticmethod
    def _read_text(path: Path, encoding: str) -> str:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            return path.read_text(encoding="gb18030")


def _in_window(value: object, window: TimeWindow) -> bool:
    if not isinstance(value, datetime):
        return False
    return window.start_at <= value < window.end_at

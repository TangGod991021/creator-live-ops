from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CsvMappingError(ValueError):
    pass


@dataclass(frozen=True)
class CsvMapping:
    dataset: str
    resource: str
    target_table: str
    encoding: str
    delimiter: str
    window_column: str | None
    key_columns: tuple[str, ...]
    required: tuple[str, ...]
    datetime_columns: tuple[str, ...]
    decimal_columns: tuple[str, ...]
    on_error: str
    fields: dict[str, str]


def load_mapping(path: Path) -> CsvMapping:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CsvMappingError(f"{path}: mapping must be a mapping")
    for key in ("dataset", "resource", "target_table", "key_columns", "fields"):
        if key not in data:
            raise CsvMappingError(f"{path}: missing {key}")
    fields = data["fields"]
    if not isinstance(fields, dict) or not fields:
        raise CsvMappingError(f"{path}: fields must be a non-empty mapping")
    targets = {str(value) for value in fields.values()}
    key_columns = tuple(str(value) for value in data["key_columns"])
    for column in key_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: key column {column} is not mapped")
    required = tuple(str(value) for value in data.get("required", key_columns))
    for column in required:
        if column not in targets:
            raise CsvMappingError(f"{path}: required column {column} is not mapped")
    datetime_columns = tuple(str(value) for value in data.get("datetime_columns", ()))
    decimal_columns = tuple(str(value) for value in data.get("decimal_columns", ()))
    for column in datetime_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: datetime_columns contains unmapped {column}")
    for column in decimal_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: decimal_columns contains unmapped {column}")
    on_error = str(data.get("on_error", "skip"))
    if on_error not in {"skip", "raise"}:
        raise CsvMappingError(f"{path}: on_error must be skip or raise")
    window_column = data.get("window_column")
    if window_column is not None:
        window_column = str(window_column)
        if window_column not in targets:
            raise CsvMappingError(f"{path}: window_column {window_column} is not mapped")
    return CsvMapping(
        dataset=str(data["dataset"]),
        resource=str(data["resource"]),
        target_table=str(data["target_table"]),
        encoding=str(data.get("encoding", "utf-8-sig")),
        delimiter=str(data.get("delimiter", ",")),
        window_column=window_column,
        key_columns=key_columns,
        required=required,
        datetime_columns=datetime_columns,
        decimal_columns=decimal_columns,
        on_error=on_error,
        fields={str(key): str(value) for key, value in fields.items()},
    )


def load_mappings(directory: Path) -> dict[str, CsvMapping]:
    mappings: dict[str, CsvMapping] = {}
    for path in sorted(directory.glob("*.yml")):
        mapping = load_mapping(path)
        if mapping.resource in mappings:
            raise CsvMappingError(f"{path}: duplicate resource {mapping.resource}")
        mappings[mapping.resource] = mapping
    return mappings

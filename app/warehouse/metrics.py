from pathlib import Path
from typing import Any

import yaml


class MetricDefinitionError(ValueError):
    pass


def load_metrics(path: Path) -> dict[str, dict[str, Any]]:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MetricDefinitionError(f"{path}: metrics file must contain a mapping")
    metrics = data.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise MetricDefinitionError(f"{path}: metrics must be a mapping")
    for name, definition in metrics.items():
        if not isinstance(definition, dict):
            raise MetricDefinitionError(f"{name}: metric definition must be a mapping")
        for key in ("name", "source", "formula", "attribution"):
            if key not in definition:
                raise MetricDefinitionError(f"{name}: missing {key}")
    return metrics

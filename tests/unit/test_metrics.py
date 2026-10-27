from pathlib import Path

from app.warehouse.metrics import load_metrics


def test_metrics_yaml_loads() -> None:
    metrics = load_metrics(Path("metrics/metrics.yml"))
    assert "gmv" in metrics
    assert metrics["gmv"]["formula"] == "SUM(pay_amount)"
    assert metrics["gmv"]["attribution"] == "pay_time"


def test_every_metric_has_required_keys() -> None:
    metrics = load_metrics(Path("metrics/metrics.yml"))
    for name, definition in metrics.items():
        for key in ("name", "source", "formula", "attribution"):
            assert key in definition, f"{name} missing {key}"

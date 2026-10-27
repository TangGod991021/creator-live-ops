from pathlib import Path

import pytest

from app.warehouse.dag import DagError, topological_order
from app.warehouse.model import SqlModel


def model(name: str, deps: tuple[str, ...]) -> SqlModel:
    return SqlModel(
        layer=name.split("_")[0],
        target=name,
        depends_on=deps,
        incremental_key=None,
        window="day",
        sql="",
        path=Path(f"{name}.sql"),
    )


def test_topological_order() -> None:
    models = {
        "ads_demo": model("ads_demo", ("dws_demo",)),
        "dws_demo": model("dws_demo", ("dwd_demo",)),
        "dwd_demo": model("dwd_demo", ("ods_demo",)),
        "ods_demo": model("ods_demo", ()),
    }
    assert topological_order(models) == ["ods_demo", "dwd_demo", "dws_demo", "ads_demo"]


def test_missing_dependency_rejected() -> None:
    models = {"dwd_demo": model("dwd_demo", ("ods_missing",))}
    with pytest.raises(DagError, match="missing dependency"):
        topological_order(models)


def test_cycle_rejected() -> None:
    models = {
        "a": model("a", ("b",)),
        "b": model("b", ("a",)),
    }
    with pytest.raises(DagError, match="cycle"):
        topological_order(models)

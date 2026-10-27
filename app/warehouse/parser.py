import re
from pathlib import Path

from app.warehouse.model import SqlModel

_HEADER = re.compile(r"^--[ \t]*@(\w+):[ \t]*(.*)$", re.MULTILINE)
_REQUIRED = ("layer", "target", "window")


class ModelParseError(ValueError):
    pass


def parse_model(path: Path) -> SqlModel:
    text = path.read_text(encoding="utf-8")
    meta = {m.group(1): m.group(2).strip() for m in _HEADER.finditer(text)}
    for key in _REQUIRED:
        if not meta.get(key):
            raise ModelParseError(f"{path}: missing {key}")
    depends_on = tuple(
        item.strip() for item in meta.get("depends_on", "").split(",") if item.strip()
    )
    return SqlModel(
        layer=meta["layer"],
        target=meta["target"],
        depends_on=depends_on,
        incremental_key=meta.get("incremental_key") or None,
        window=meta["window"],
        sql=text,
        path=path,
    )


def load_models(directory: Path) -> dict[str, SqlModel]:
    models: dict[str, SqlModel] = {}
    for path in sorted(directory.glob("*.sql")):
        model = parse_model(path)
        if model.target in models:
            raise ModelParseError(f"duplicate model target: {model.target}")
        models[model.target] = model
    return models

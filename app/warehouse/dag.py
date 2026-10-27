from app.warehouse.model import SqlModel


class DagError(ValueError):
    pass


def topological_order(models: dict[str, SqlModel]) -> list[str]:
    for name, model in models.items():
        for dep in model.depends_on:
            if dep not in models:
                raise DagError(f"{name}: missing dependency {dep}")

    indegree = {name: len(model.depends_on) for name, model in models.items()}
    children: dict[str, list[str]] = {name: [] for name in models}
    for name, model in models.items():
        for dep in model.depends_on:
            children[dep].append(name)

    ready = sorted(name for name, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        name = ready.pop(0)
        order.append(name)
        for child in sorted(children[name]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()

    if len(order) != len(models):
        remaining = sorted(set(models) - set(order))
        raise DagError(f"cycle detected among: {remaining}")
    return order

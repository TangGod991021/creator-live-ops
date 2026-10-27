from pathlib import Path
from typing import Any

import yaml
from croniter import croniter

from app.scheduler.models import JobDefinition, RetryPolicy


class JobConfigError(ValueError):
    pass


def load_job_file(path: Path) -> JobDefinition:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise JobConfigError(f"{path}: job file must contain a mapping")
    for key in ("id", "lane", "schedule", "resource", "window"):
        if key not in data:
            raise JobConfigError(f"{path}: missing {key}")
    if len(str(data["id"])) > 100:
        raise JobConfigError(f"{path}: id must be at most 100 characters")
    if not croniter.is_valid(str(data["schedule"])):
        raise JobConfigError(f"{path}: invalid cron expression")
    retry_data = data.get("retry") or {}
    if not isinstance(retry_data, dict):
        raise JobConfigError(f"{path}: retry must be a mapping")
    depends_on = data.get("depends_on") or ()
    if not isinstance(depends_on, list | tuple):
        raise JobConfigError(f"{path}: depends_on must be a list")
    enabled_value = data.get("enabled", True)
    if isinstance(enabled_value, bool):
        enabled = enabled_value
    elif isinstance(enabled_value, str) and enabled_value.lower() in {"true", "false"}:
        enabled = enabled_value.lower() == "true"
    else:
        raise JobConfigError(f"{path}: enabled must be a boolean")
    return JobDefinition(
        id=str(data["id"]),
        lane=str(data["lane"]),
        schedule=str(data["schedule"]),
        resource=str(data["resource"]),
        window=str(data["window"]),
        depends_on=tuple(str(item) for item in depends_on),
        retry=RetryPolicy(
            max_attempts=int(retry_data.get("max_attempts", 3)),
            backoff_seconds=int(retry_data.get("backoff_seconds", 30)),
        ),
        timeout_seconds=int(data.get("timeout_seconds", 900)),
        enabled=enabled,
    )


def load_jobs(directory: Path) -> dict[str, JobDefinition]:
    jobs: dict[str, JobDefinition] = {}
    for path in sorted(directory.glob("*.yml")):
        job = load_job_file(path)
        if job.id in jobs:
            raise JobConfigError(f"duplicate job id: {job.id}")
        jobs[job.id] = job
    return jobs

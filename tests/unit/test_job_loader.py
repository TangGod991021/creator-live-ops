from pathlib import Path

import pytest

from app.scheduler.loader import JobConfigError, load_job_file, load_jobs


def write_job(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_load_valid_job(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "demo.yml",
        """
id: demo_pipeline
lane: csv_import
schedule: "*/5 * * * *"
resource: demo
window: day
depends_on: []
retry:
  max_attempts: 2
  backoff_seconds: 5
timeout_seconds: 300
enabled: true
""",
    )
    job = load_job_file(path)
    assert job.id == "demo_pipeline"
    assert job.lane == "csv_import"
    assert job.retry.max_attempts == 2


def test_invalid_cron_rejected(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "bad.yml",
        """
id: bad
lane: l1
schedule: "not-a-cron"
resource: demo
window: day
""",
    )
    with pytest.raises(JobConfigError, match="invalid cron"):
        load_job_file(path)


def test_quoted_false_enabled_is_disabled(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "disabled.yml",
        """
id: disabled
lane: l1
schedule: "0 * * * *"
resource: demo
window: hour
enabled: "false"
""",
    )
    assert load_job_file(path).enabled is False


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    body = """
id: same
lane: l1
schedule: "0 * * * *"
resource: demo
window: hour
"""
    write_job(tmp_path, "a.yml", body)
    write_job(tmp_path, "b.yml", body)
    with pytest.raises(JobConfigError, match="duplicate job id"):
        load_jobs(tmp_path)


def test_ingest_job_requires_adapter(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "ingest.yml",
        """
id: ingest_orders
lane: csv_import
schedule: "0 1 * * *"
resource: orders
window: day
kind: ingest
""",
    )
    with pytest.raises(JobConfigError, match="adapter"):
        load_job_file(path)


def test_ingest_job_parses_adapter(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "ingest.yml",
        """
id: ingest_orders
lane: csv_import
schedule: "0 1 * * *"
resource: orders
window: day
kind: ingest
adapter: csv_import
""",
    )
    job = load_job_file(path)
    assert job.kind == "ingest"
    assert job.adapter == "csv_import"

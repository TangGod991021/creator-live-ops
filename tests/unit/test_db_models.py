from app.db.models import Base


def test_system_tables_registered() -> None:
    names = set(Base.metadata.tables)
    expected = {
        "sys_config",
        "sys_job_lock",
        "etl_run",
        "etl_model_run",
        "etl_quality_result",
        "etl_watermark",
        "audit_secret_access",
    }
    assert expected <= names

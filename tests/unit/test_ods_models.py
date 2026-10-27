def test_ods_tables_registered() -> None:
    import app.db.ods_models  # noqa: F401
    from app.db.models import Base

    names = set(Base.metadata.tables)
    expected = {
        "ods_order",
        "ods_after_sale",
        "ods_settlement",
        "ods_live_room",
        "ods_ad_cost",
        "ods_fetch_log",
    }
    assert expected <= names


def test_ods_order_primary_key() -> None:
    import app.db.ods_models as ods

    pk = [column.name for column in ods.OdsOrder.__table__.primary_key.columns]
    assert pk == ["platform", "order_id"]


def test_ods_ad_cost_primary_key_order() -> None:
    import app.db.ods_models as ods

    pk = [column.name for column in ods.OdsAdCost.__table__.primary_key.columns]
    assert pk == ["platform", "account_id", "stat_time", "granularity"]

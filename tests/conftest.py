import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base


@pytest.fixture
async def db_engine():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 to run integration tests")
    url = os.getenv(
        "DATABASE_URL",
        "mysql+asyncmy://root:root@127.0.0.1:3306/ecom_ops?charset=utf8mb4",
    )
    import app.db.demo_models  # noqa: F401

    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name}"))
    yield engine
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name}"))
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    Session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with Session() as session:
        yield session

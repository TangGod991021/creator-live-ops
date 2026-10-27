from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class JobLock:
    def __init__(self, session: AsyncSession, owner: str, ttl_seconds: int = 3600) -> None:
        self._session = session
        self._owner = owner
        self._ttl = ttl_seconds

    async def acquire(self, job_id: str) -> bool:
        await self._session.execute(
            text(
                """
                INSERT IGNORE INTO sys_job_lock (job_id, lock_owner, locked_until)
                VALUES (:job_id, :owner, DATE_ADD(NOW(), INTERVAL :ttl SECOND))
                """
            ),
            {"job_id": job_id, "owner": self._owner, "ttl": self._ttl},
        )
        await self._session.execute(
            text(
                """
                UPDATE sys_job_lock
                SET lock_owner = :owner,
                    locked_until = DATE_ADD(NOW(), INTERVAL :ttl SECOND)
                WHERE job_id = :job_id
                  AND (lock_owner = :owner OR locked_until < NOW())
                """
            ),
            {"job_id": job_id, "owner": self._owner, "ttl": self._ttl},
        )
        # MySQL 的 rowcount 默认是“实际变更行数”：首次 INSERT 后同秒内 UPDATE
        # 写入相同 locked_until 会返回 0，因此以锁持有者为准判断是否成功。
        owner = (
            await self._session.execute(
                text("SELECT lock_owner FROM sys_job_lock WHERE job_id = :job_id"),
                {"job_id": job_id},
            )
        ).scalar_one_or_none()
        await self._session.commit()
        return owner == self._owner

    async def release(self, job_id: str) -> None:
        await self._session.execute(
            text(
                """
                UPDATE sys_job_lock
                SET locked_until = DATE_SUB(NOW(), INTERVAL 1 SECOND)
                WHERE job_id = :job_id AND lock_owner = :owner
                """
            ),
            {"job_id": job_id, "owner": self._owner},
        )
        await self._session.commit()

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: int = 30


@dataclass(frozen=True)
class JobDefinition:
    id: str
    lane: str
    schedule: str
    resource: str
    window: str
    depends_on: tuple[str, ...] = ()
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: int = 900
    enabled: bool = True

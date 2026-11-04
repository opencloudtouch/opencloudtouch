"""Domain models of the stream recovery feature."""

from dataclasses import dataclass

DEFAULT_MIN_PLAY_SECONDS = 600
DEFAULT_MAX_ATTEMPTS_PER_HOUR = 3

OUTCOME_RESUMED = "resumed"
OUTCOME_GAVE_UP = "gave_up"
OUTCOME_SKIPPED_NO_PRESET = "skipped_no_preset"
OUTCOME_SKIPPED_RATE_LIMITED = "skipped_rate_limited"
OUTCOMES = (
    OUTCOME_RESUMED,
    OUTCOME_GAVE_UP,
    OUTCOME_SKIPPED_NO_PRESET,
    OUTCOME_SKIPPED_RATE_LIMITED,
)


@dataclass
class StreamRecoveryConfig:
    """Opt-in watchdog settings (a missing row reads as these defaults)."""

    enabled: bool = False
    min_play_seconds: int = DEFAULT_MIN_PLAY_SECONDS
    max_attempts_per_hour: int = DEFAULT_MAX_ATTEMPTS_PER_HOUR
    updated_at: str | None = None


@dataclass
class StreamRecoveryEvent:
    """One entry of the activity log. Holds no exception text, IPs or URLs."""

    occurred_at: str
    device_id: str
    outcome: str
    preset_number: int | None = None
    station_name: str | None = None
    play_seconds: int | None = None
    attempts: int = 0
    error_code: str | None = None
    id: int | None = None

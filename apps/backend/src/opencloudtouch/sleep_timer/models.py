"""Domain model of the sleep timer."""

from dataclasses import dataclass

END_ACTION_STOP = "stop"
END_ACTION_STANDBY = "standby"
END_ACTIONS = (END_ACTION_STOP, END_ACTION_STANDBY)

MIN_DURATION_MINUTES = 1
MAX_DURATION_MINUTES = 720
MAX_FADE_SECONDS = 300
DEFAULT_FADE_SECONDS = 30


@dataclass
class SleepTimer:
    """One active timer. Times are UTC epoch seconds (the service's wall clock)."""

    device_id: str
    ends_at: float
    duration_minutes: int
    fade_seconds: int
    end_action: str
    original_volume: int | None = None
    created_at: float = 0.0

    @property
    def fade_start(self) -> float:
        return self.ends_at - self.fade_seconds

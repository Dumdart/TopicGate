from enum import StrEnum


class ObservationStatus(StrEnum):
    """Whether a current topic value was restored or observed live."""

    LIVE = "live"
    CACHED = "cached"

"""Time parsing utilities for pmlogsynth profiles."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from pmlogsynth.profile import ValidationError


def _pmapi_parse_interval(interval_str: str) -> float:
    """Thin shim: import pcp.pmapi and call pmParseInterval. Raises on failure."""
    try:
        import pcp.pmapi as pmapi  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(f"PCP not available: {exc}") from exc
    ctx = pmapi.pmContext()
    result = ctx.pmParseInterval(interval_str)
    return float(result)


def pcp_parse_interval(interval_str: str) -> int:
    """Parse a PCP interval string to whole seconds via pmParseInterval.

    Raises ValidationError if PCP is unavailable or the string is invalid.
    """
    try:
        seconds = _pmapi_parse_interval(interval_str)
    except ImportError as exc:
        raise ValidationError(
            f"PCP is required to parse interval strings: {exc}"
        ) from exc
    except Exception as exc:
        raise ValidationError(
            f"Invalid interval {interval_str!r}: {exc}. "
            f"Use a PCP interval string like '90s', '10m', '1h30m', '2days'."
        ) from exc
    return int(seconds)


def parse_absolute_timestamp(raw: str, field: str = "meta.start") -> datetime:
    """Parse an absolute timestamp string to a UTC-aware datetime.

    Accepts the six standard formats used by both profile.py and cli.py.
    Raises ValidationError naming the field if no format matches.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S UTC",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValidationError(
        f"{field}: cannot parse {raw!r}. "
        f"Use ISO 8601 (e.g. 2026-03-02T00:00:00Z) or 'YYYY-MM-DD HH:MM:SS UTC'."
    )


def parse_relative_starttime(raw: str, now: Optional[datetime] = None) -> datetime:
    """Parse a relative time offset like '-90m' to an absolute UTC datetime.

    The offset is subtracted from `now` (defaults to current UTC time).
    Raises ValidationError for malformed or positive offsets.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    if raw.startswith("+"):
        raise ValidationError(
            f"meta.start: {raw!r} — only past-anchored offsets supported "
            f"(use '-90m', not '+90m')"
        )

    if not raw.startswith("-"):
        raise ValidationError(
            f"meta.start: {raw!r} — relative start must begin with '-' (e.g. '-90m')"
        )

    interval_str = raw[1:]
    if not interval_str:
        raise ValidationError(
            f"meta.start: {raw!r} — missing interval after '-' (e.g. '-90m')"
        )

    offset_seconds = pcp_parse_interval(interval_str)
    return now - timedelta(seconds=offset_seconds)

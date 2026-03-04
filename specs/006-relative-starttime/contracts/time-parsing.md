# Contract: time_parsing module

**Module**: `pmlogsynth.time_parsing`
**Type**: Internal utility module (no public CLI surface)
**Date**: 2026-03-04

## Function contracts

### `pcp_parse_interval(interval_str: str) -> int`

**Purpose**: Thin wrapper around PCP's `pmParseInterval`. Lazy-imports `pcp.pmapi`.

**Inputs**:
- `interval_str`: A non-empty PCP interval string with no leading sign (e.g., `"90m"`, `"1h30m"`, `"2days"`).

**Outputs**:
- `int`: Duration in whole seconds (≥ 0).

**Errors**:
- `ValidationError`: If `pmParseInterval` raises, or if the result is not a non-negative integer.

**Side effects**: None. Does not modify state.

**PCP availability**: Raises `ValidationError` (not `ImportError`) if `pcp.pmapi` is unavailable, with a message indicating PCP is required.

---

### `parse_absolute_timestamp(raw: str, field: str = "meta.start") -> datetime`

**Purpose**: Parse an absolute timestamp string to a UTC-aware `datetime`. Replaces both `_parse_start_for_meta` (profile.py) and `_parse_start_time` (cli.py).

**Inputs**:
- `raw`: A timestamp string in one of the accepted formats below.
- `field`: Field name for error messages (default `"meta.start"`).

**Accepted formats** (tried in order):
1. `%Y-%m-%dT%H:%M:%SZ`
2. `%Y-%m-%dT%H:%M:%S+00:00`
3. `%Y-%m-%dT%H:%M:%S`
4. `%Y-%m-%d %H:%M:%S UTC`
5. `%Y-%m-%d %H:%M:%S`
6. `%Y-%m-%dT%H:%M:%S%z`

**Outputs**:
- `datetime`: UTC-aware (`tzinfo=timezone.utc`).

**Errors**:
- `ValidationError`: If none of the accepted formats match. Message includes `field` name and an example.

---

### `parse_relative_starttime(raw: str, now: Optional[datetime] = None) -> datetime`

**Purpose**: Parse a relative time expression to an absolute UTC `datetime`.

**Inputs**:
- `raw`: String of the form `-<interval>` (e.g., `"-90m"`, `"-1h30m"`, `"-2days"`).
- `now`: Reference "now" for resolution. Defaults to `datetime.now(tz=timezone.utc)` at call time if `None`. Accepting an explicit `now` makes the function deterministic in tests.

**Outputs**:
- `datetime`: UTC-aware; equals `now - timedelta(seconds=offset_seconds)`.

**Errors**:
- `ValidationError`: If `raw` does not start with `-`.
- `ValidationError`: If `raw` starts with `+` (positive offsets not supported).
- `ValidationError`: If `raw` is exactly `"-"` (no interval portion).
- `ValidationError`: If the interval portion fails `pcp_parse_interval`.

---

## Profile YAML contract (meta.start)

```yaml
meta:
  # Absolute timestamp — existing behaviour, unchanged
  start: "2025-01-15 09:00:00 UTC"

  # Relative — NEW: any PCP interval string prefixed with '-'
  start: -90m
  start: -2h
  start: -1h30m
  start: -3days
  start: -0s         # resolves to ~now
```

The field value is always resolved to an absolute UTC `datetime` before being stored in `ProfileMeta.start`. Consumers of `ProfileMeta` (e.g., `timeline.py`) are unaffected.

## Tier 1 test mocking pattern

```python
from unittest.mock import patch

# Mocking pcp_parse_interval in the profile module (for parse_duration tests)
with patch("pmlogsynth.profile.pcp_parse_interval", return_value=86400) as mock_pcp:
    result = parse_duration("1d")
assert result == 86400
mock_pcp.assert_called_once_with("1d")

# Mocking pcp_parse_interval in time_parsing (for parse_relative_starttime tests)
with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400) as mock_pcp:
    result = parse_relative_starttime("-90m", now=fixed_now)
assert result == fixed_now - timedelta(seconds=5400)
```

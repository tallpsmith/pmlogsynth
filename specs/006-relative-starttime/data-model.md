# Data Model: Relative Start Time in Profiles

**Branch**: `006-relative-starttime` | **Date**: 2026-03-04

## Entities

### RelativeTimeExpression

A string value for `meta.start` that specifies a past-anchored offset.

| Field | Type | Constraints |
|-------|------|-------------|
| raw | `str` | Starts with `-`; remainder is a valid PCP interval string |
| sign | `"-"` | Always `-`; positive offsets are rejected |
| interval_str | `str` | The portion after `-`; valid input for `pmParseInterval` |
| resolved_seconds | `int` | Result of `pcp_parse_interval(interval_str)`; must be ≥ 0 |

**Valid examples**: `-90m`, `-2h`, `-1h30m`, `-3d`, `-1day`, `-45minutes`
**Invalid examples**: `+30m` (positive), `-` (bare dash), `-90x` (unknown unit), `ago1hour` (missing dash)

### ResolvedStartTime

The absolute UTC `datetime` produced by applying a relative expression to a reference "now".

| Field | Type | Constraints |
|-------|------|-------------|
| value | `datetime` | UTC-aware; `tzinfo=timezone.utc` |
| source | `"relative"` or `"absolute"` or `"default"` | Tracks how start was determined |

**State transitions for `meta.start`**:

```
meta.start absent  → ResolvedStartTime(source="default")  [today midnight UTC, existing behaviour]
meta.start absolute → ResolvedStartTime(source="absolute") [parse_absolute_timestamp]
meta.start relative → ResolvedStartTime(source="relative") [parse_relative_starttime]
--start CLI flag   → overrides all profile-derived values  [parse_absolute_timestamp, absolute only]
```

### PcpIntervalString (value object)

Passed into `pcp_parse_interval`. Must conform to PCP's `pmParseInterval` grammar:

| Unit class | Accepted tokens |
|------------|-----------------|
| Seconds | `s`, `sec`, `secs`, `second`, `seconds` |
| Minutes | `m`, `min`, `mins`, `minute`, `minutes` |
| Hours | `h`, `hour`, `hours` |
| Days | `d`, `day`, `days` |

Compound forms (e.g., `1h30m`, `4d6h`) are additive and accepted. Floats (e.g., `4d6.5h`) may be accepted by PCP but produce non-integer seconds — the wrapping validation must handle this.

## Validation Rules

| Rule | Where enforced | Error raised |
|------|---------------|--------------|
| Relative expression must start with `-` | `parse_relative_starttime` | `ValidationError` |
| Positive offset (`+…`) is rejected | `parse_relative_starttime` | `ValidationError` |
| Bare `-` (no interval) is rejected | `parse_relative_starttime` | `ValidationError` |
| PCP interval parse failure → validation error | `pcp_parse_interval` → `ValidationError` | `ValidationError` |
| `parse_duration` result must be > 0 | `parse_duration` in `profile.py` | `ValidationError` |
| `parse_duration` plain int must be > 0 | `parse_duration` in `profile.py` | `ValidationError` |

## Existing model fields (unchanged)

```
WorkloadProfile
└── meta: ProfileMeta
    └── start: Optional[datetime]   ← extended to accept relative input at parse time;
                                       stored as resolved UTC datetime after parsing
```

No new dataclass fields. The `start` field on `ProfileMeta` remains `Optional[datetime]` — the relative-vs-absolute distinction is handled at parse time and discarded after resolution.

"""Centralised PCP constants — single source of truth for the package.

When ``python3-pcp`` is installed, all values are imported from PCP's
``cpmapi`` C-API bindings.  When it is not available (CI quality jobs,
Tier 1/2 tests), well-known fallback integers from the stable PCP ABI
are used instead so that domain modules remain importable.

Pre-built unit tuples are derived from these constants and provided as
convenience values for use in ``MetricDescriptor.units``.
"""

from typing import Tuple

try:
    import cpmapi as _c

    # Metric types
    PM_TYPE_FLOAT: int = _c.PM_TYPE_FLOAT
    PM_TYPE_U64: int = _c.PM_TYPE_U64

    # Metric semantics
    PM_SEM_COUNTER: int = _c.PM_SEM_COUNTER
    PM_SEM_DISCRETE: int = _c.PM_SEM_DISCRETE
    PM_SEM_INSTANT: int = _c.PM_SEM_INSTANT

    # Dimension scales (internal — used only to build unit tuples)
    _SPACE_BYTE: int = _c.PM_SPACE_BYTE
    _SPACE_KBYTE: int = _c.PM_SPACE_KBYTE
    _TIME_MSEC: int = _c.PM_TIME_MSEC

except ImportError:
    # Stable PCP ABI values — these have not changed across PCP releases.
    PM_TYPE_FLOAT = 4
    PM_TYPE_U64 = 3

    PM_SEM_COUNTER = 1
    PM_SEM_DISCRETE = 4
    PM_SEM_INSTANT = 3

    _SPACE_BYTE = 0
    _SPACE_KBYTE = 1
    _TIME_MSEC = 2

# ------------------------------------------------------------------
# Pre-built unit tuples  (dimSpace, dimTime, dimCount,
#                          scaleSpace, scaleTime, scaleCount)
# These are the argument vectors passed to pmi.pmiUnits().
# ------------------------------------------------------------------
_Units = Tuple[int, int, int, int, int, int]

UNITS_NONE: _Units = (0, 0, 0, 0, 0, 0)
UNITS_COUNT: _Units = (0, 0, 1, 0, 0, 0)
UNITS_MSEC: _Units = (0, 1, 0, 0, _TIME_MSEC, 0)
UNITS_BYTES: _Units = (1, 0, 0, _SPACE_BYTE, 0, 0)
UNITS_KBYTE: _Units = (1, 0, 0, _SPACE_KBYTE, 0, 0)

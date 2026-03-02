"""Centralised PCP constants — single source of truth for the package.

All type, semantic, and unit-scale constants are imported directly from
PCP's ``cpmapi`` C-API bindings.  This requires ``python3-pcp`` to be
installed (system package).

Pre-built unit tuples are derived from these constants and provided as
convenience values for use in ``MetricDescriptor.units``.
"""

from typing import Tuple

import cpmapi as _c

# ------------------------------------------------------------------
# Metric types  (PM_TYPE_*)
# ------------------------------------------------------------------
PM_TYPE_FLOAT: int = _c.PM_TYPE_FLOAT
PM_TYPE_U64: int = _c.PM_TYPE_U64

# ------------------------------------------------------------------
# Metric semantics  (PM_SEM_*)
# ------------------------------------------------------------------
PM_SEM_COUNTER: int = _c.PM_SEM_COUNTER
PM_SEM_DISCRETE: int = _c.PM_SEM_DISCRETE
PM_SEM_INSTANT: int = _c.PM_SEM_INSTANT

# ------------------------------------------------------------------
# Pre-built unit tuples  (dimSpace, dimTime, dimCount,
#                          scaleSpace, scaleTime, scaleCount)
# These are the argument vectors passed to pmi.pmiUnits().
# Derived from cpmapi's native scale constants (PM_SPACE_*, PM_TIME_*).
# ------------------------------------------------------------------
_Units = Tuple[int, int, int, int, int, int]

UNITS_NONE: _Units = (0, 0, 0, 0, 0, 0)
UNITS_COUNT: _Units = (0, 0, 1, 0, 0, 0)
UNITS_MSEC: _Units = (0, 1, 0, 0, _c.PM_TIME_MSEC, 0)
UNITS_BYTES: _Units = (1, 0, 0, _c.PM_SPACE_BYTE, 0, 0)
UNITS_KBYTE: _Units = (1, 0, 0, _c.PM_SPACE_KBYTE, 0, 0)

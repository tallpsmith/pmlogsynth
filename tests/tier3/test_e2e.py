"""Tier 3 E2E tests — require real pcp.pmi (conditionally skipped if absent).

Full E2E implementation is in Phase 8 (T040). This stub ensures the tier3
directory is never empty so CI's pytest run always exits 0 when PCP is present.
"""

import pytest


@pytest.mark.tier3
def test_pcp_library_available(pcp_available: bool) -> None:
    """Verify pcp.pmi is importable (fixture skips if not)."""
    assert pcp_available


@pytest.mark.tier3
def test_pcp_pmi_diagnostics(pcp_available: bool) -> None:
    """Log available pcp.pmi attributes for diagnostic purposes; always passes."""
    import pcp.pmi as pmi

    attrs = [a for a in dir(pmi) if not a.startswith("_")]
    # Print for CI log visibility
    print(f"\npcp.pmi public attributes: {attrs}")
    # Just verify the module loaded — attribute inspection is informational only
    assert isinstance(attrs, list)

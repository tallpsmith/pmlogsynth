"""Tier 3 E2E tests — require real pcp.pmi (conditionally skipped if absent).

Full E2E implementation is in Phase 8 (T040). This stub ensures the tier3
directory is never empty so CI's pytest run always exits 0.
"""

import pytest


@pytest.mark.tier3
def test_pcp_library_available(pcp_available: bool) -> None:
    """Verify pcp.pmi is importable (fixture skips if not)."""
    assert pcp_available


@pytest.mark.tier3
def test_pcp_pmi_import(pcp_available: bool) -> None:
    """Verify basic pcp.pmi attributes are accessible."""
    import pcp.pmi as pmi  # noqa: F401

    public_attrs = [a for a in dir(pmi) if not a.startswith("_")]
    assert hasattr(pmi, "pmiLogImport"), (
        "pmiLogImport not found in pcp.pmi; available: %s" % public_attrs
    )


@pytest.mark.tier3
def test_pcp_pmi_id_functions(pcp_available: bool) -> None:
    """Check pmiID / pmiInDom availability (may be methods on pmiLogImport instead)."""
    import pcp.pmi as pmi

    # These may be module-level functions or methods on pmiLogImport — log presence
    has_pmiID = hasattr(pmi, "pmiID")
    has_pmiInDom = hasattr(pmi, "pmiInDom")
    has_cls_pmiID = hasattr(pmi.pmiLogImport, "pmiID")
    has_cls_pmiInDom = hasattr(pmi.pmiLogImport, "pmiInDom")

    # At least one of module-level or class-level must provide each
    assert has_pmiID or has_cls_pmiID, (
        "pmiID not found at module or class level; module attrs: %s"
        % [a for a in dir(pmi) if not a.startswith("_")]
    )
    assert has_pmiInDom or has_cls_pmiInDom, (
        "pmiInDom not found at module or class level; module attrs: %s"
        % [a for a in dir(pmi) if not a.startswith("_")]
    )

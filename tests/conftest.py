"""pytest configuration: tier markers and PCP availability detection."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "tier1: unit tests, no PCP required")
    config.addinivalue_line("markers", "tier2: integration tests, PCP layer mocked")
    config.addinivalue_line("markers", "tier3: E2E tests, real PCP library required")


def _pcp_importable() -> bool:
    """Return True if pcp.pmi can be imported."""
    try:
        import pcp.pmi  # noqa: F401

        return True
    except ImportError:
        return False


_PCP_AVAILABLE = _pcp_importable()


@pytest.fixture(scope="session")
def pcp_available() -> bool:
    """Skip test if pcp.pmi is not importable (Tier 3 guard)."""
    if not _PCP_AVAILABLE:
        pytest.skip("WARNING: PCP library not available — E2E tests skipped")
    return True

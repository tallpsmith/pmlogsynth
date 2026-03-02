"""pytest configuration: tier markers and PCP availability detection."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "tier1: unit tests, no PCP required")
    config.addinivalue_line("markers", "tier2: integration tests, PCP layer mocked")
    config.addinivalue_line("markers", "tier3: E2E tests, real PCP library required")


@pytest.fixture(scope="session")
def pcp_available() -> bool:
    """Skip test if pcp.pmi is not importable (Tier 3 guard)."""
    try:
        import pcp.pmi  # noqa: F401

        return True
    except ImportError:
        pytest.skip(
            "WARNING: PCP library not available — E2E tests skipped",
            allow_module_level=False,
        )
        return False  # unreachable; satisfies type checker

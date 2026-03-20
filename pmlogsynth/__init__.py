"""pmlogsynth — synthetic PCP archive generator."""

__version__: str

try:
    from pmlogsynth._version import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

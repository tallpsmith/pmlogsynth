"""CLI entry point for pmlogsynth."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pmlogsynth.profile import ProfileResolver, ValidationError, WorkloadProfile

# ---------------------------------------------------------------------------
# Metric names (from cli-schema.md — sorted lexicographically)
# ---------------------------------------------------------------------------

_ALL_METRIC_NAMES: List[str] = [
    "disk.all.read",
    "disk.all.read_bytes",
    "disk.all.write",
    "disk.all.write_bytes",
    "disk.dev.avactive",
    "disk.dev.avg_qlen",
    "disk.dev.blkread",
    "disk.dev.blkwrite",
    "disk.dev.read",
    "disk.dev.read_bytes",
    "disk.dev.read_merge",
    "disk.dev.read_rawactive",
    "disk.dev.write",
    "disk.dev.write_bytes",
    "disk.dev.write_merge",
    "disk.dev.write_rawactive",
    "hinv.ncpu",
    "kernel.all.blocked",
    "kernel.all.cpu.guest",
    "kernel.all.cpu.guest_nice",
    "kernel.all.cpu.idle",
    "kernel.all.cpu.intr",
    "kernel.all.cpu.nice",
    "kernel.all.cpu.steal",
    "kernel.all.cpu.sys",
    "kernel.all.cpu.user",
    "kernel.all.cpu.vnice",
    "kernel.all.cpu.vuser",
    "kernel.all.cpu.wait.total",
    "kernel.all.intr",
    "kernel.all.load",
    "kernel.all.pswitch",
    "kernel.all.running",
    "kernel.percpu.cpu.idle",
    "kernel.percpu.cpu.sys",
    "kernel.percpu.cpu.user",
    "mem.physmem",
    "mem.util.active",
    "mem.util.bufmem",
    "mem.util.cached",
    "mem.util.free",
    "mem.util.inactive",
    "mem.util.slab",
    "mem.util.used",
    "mem.vmstat.pgpgin",
    "mem.vmstat.pgpgout",
    "network.interface.in.bytes",
    "network.interface.in.packets",
    "network.interface.out.bytes",
    "network.interface.out.packets",
    "swap.pagesin",
    "swap.pagesout",
    "swap.used",
]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pmlogsynth",
        description="Generate synthetic PCP archives from declarative YAML profiles.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    # Top-level informational flags
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        default=False,
        help="List all available hardware profiles and exit.",
    )
    parser.add_argument(
        "--list-metrics",
        action="store_true",
        default=False,
        help="List all PCP metric names this tool can produce and exit.",
    )
    parser.add_argument(
        "--show-schema",
        action="store_true",
        default=False,
        help="Print the profile schema context document (for AI agents) and exit.",
    )
    # -C on top level for --list-profiles
    parser.add_argument(
        "-C", "--config-dir",
        metavar="PATH",
        dest="config_dir",
        help="Additional hardware profile directory (highest precedence).",
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    # Reserve 'fleet' for Phase 3
    subparsers.add_parser("fleet", help=argparse.SUPPRESS)

    # --- generate (default, injected by _preprocess_argv when no subcommand) ---
    gen = subparsers.add_parser(
        "generate",
        help="Generate a PCP archive from a YAML workload profile (default command).",
        add_help=True,
    )
    _add_generate_args(gen)

    return parser


def _add_generate_args(p: argparse.ArgumentParser) -> None:
    """Add generate-command arguments to a parser (top-level or subcommand)."""
    p.add_argument(
        "profile",
        nargs="?",
        metavar="PROFILE",
        help="Path to YAML workload profile.",
    )
    p.add_argument(
        "-o", "--output",
        default="./pmlogsynth-out",
        metavar="PATH",
        help="Output archive base name (default: ./pmlogsynth-out).",
    )
    p.add_argument(
        "--start",
        metavar="TIMESTAMP",
        help=(
            "Archive start time (ISO 8601 or 'YYYY-MM-DD HH:MM:SS TZ'). "
            "Overrides meta.start. Default: today at 00:00:00 UTC."
        ),
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Print per-sample metric values to stderr.",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        default=False,
        help="Validate profile only; do not generate any files.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing archive files without error.",
    )
    p.add_argument(
        "--leave-partial",
        action="store_true",
        default=False,
        dest="leave_partial",
        help="On failure, leave partial output files in place.",
    )
    p.add_argument(
        "-C", "--config-dir",
        metavar="PATH",
        dest="config_dir",
        help="Additional hardware profile directory (highest precedence).",
    )


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def _parse_start_time(ts: str) -> datetime:
    """Parse --start argument into a UTC-aware datetime."""
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
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse --start timestamp {ts!r}. "
        f"Use ISO 8601 (e.g. 2024-01-15T09:00:00Z) or "
        f"'YYYY-MM-DD HH:MM:SS UTC'."
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_show_schema() -> int:
    import importlib.resources as _pkg
    try:
        text = _pkg.read_text("pmlogsynth", "schema_context.md", encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        print(f"error: schema context not found: {exc}", file=sys.stderr)
        return 1
    print(text, end="")
    return 0


def _cmd_list_metrics() -> int:
    for name in _ALL_METRIC_NAMES:
        print(name)
    return 0


def _cmd_list_profiles(config_dir: Optional[Path]) -> int:
    resolver = ProfileResolver(config_dir=config_dir)
    entries = resolver.list_all()
    print(f"{'SOURCE':<12} {'NAME'}")
    for entry in entries:
        print(f"{entry.source:<12} {entry.name}")
    return 0


def _cmd_validate(profile_path: str, config_dir: Optional[Path]) -> int:
    try:
        WorkloadProfile.from_string(
            Path(profile_path).read_text(encoding="utf-8"),
            config_dir=config_dir,
        )
        return 0
    except ValidationError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading profile: {exc}", file=sys.stderr)
        return 2


def _cmd_generate(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir) if args.config_dir else None

    # Validate --validate incompatibilities
    if args.validate:
        for flag in ("force", "leave_partial"):
            if getattr(args, flag, False):
                print(
                    f"error: --validate is incompatible with "
                    f"--{flag.replace('_', '-')}",
                    file=sys.stderr,
                )
                return 1

    if not args.profile:
        print("error: PROFILE argument is required", file=sys.stderr)
        return 1

    if args.validate:
        return _cmd_validate(args.profile, config_dir)

    # Check -C dir exists if specified
    if config_dir and not config_dir.is_dir():
        print(f"error: -C directory does not exist: {config_dir}", file=sys.stderr)
        return 2

    # Load profile
    try:
        profile_text = Path(args.profile).read_text(encoding="utf-8")
        profile = WorkloadProfile.from_string(profile_text, config_dir=config_dir)
    except ValidationError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading profile: {exc}", file=sys.stderr)
        return 2

    hardware = profile.hardware
    if hardware is None:
        print("Internal error: hardware profile not resolved", file=sys.stderr)
        return 1

    # Parse start time
    start_time = None
    if args.start:
        try:
            start_time = _parse_start_time(args.start)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    # Expand timeline
    from pmlogsynth.timeline import TimelineSequencer
    timeline = TimelineSequencer(profile).expand(start_time=start_time)

    # Write archive — lazy import so Tier 1/2 tests don't need pcp installed.
    # writer.py is a stub in Phase 1; the symbols don't exist yet.
    import importlib as _importlib

    try:
        _writer_mod = _importlib.import_module("pmlogsynth.writer")
        ArchiveWriter = _writer_mod.ArchiveWriter  # noqa: N806
        ArchiveConflictError = _writer_mod.ArchiveConflictError
        ArchiveGenerationError = _writer_mod.ArchiveGenerationError
    except (ImportError, AttributeError) as exc:
        print(f"error: PCP library not available: {exc}", file=sys.stderr)
        return 3

    from pmlogsynth.sampler import ValueSampler
    sampler = ValueSampler(noise=profile.meta.noise)

    try:
        writer = ArchiveWriter(
            output_path=args.output,
            profile=profile,
            hardware=hardware,
            force=args.force,
            leave_partial=args.leave_partial,
        )
        writer.write(timeline=timeline, sampler=sampler)
    except ArchiveConflictError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ArchiveGenerationError as exc:
        print(f"error: Archive generation failed: {exc}", file=sys.stderr)
        return 3

    return 0


# ---------------------------------------------------------------------------
# Argv pre-processing: inject 'generate' when no subcommand is given
# ---------------------------------------------------------------------------

_KNOWN_SUBCOMMANDS = {"fleet", "generate"}


def _preprocess_argv(argv: List[str]) -> List[str]:
    """Insert 'generate' at position 0 when no known subcommand is present.

    If the first non-flag positional argument is not a known subcommand,
    prepend 'generate' so all arguments are parsed by the generate subparser.
    This also handles the case where generate-specific flags like --validate
    appear before the PROFILE positional.
    """
    # Flags that consume the next token as a value
    _VALUE_FLAGS = {"-o", "--output", "--start", "-C", "--config-dir"}

    # Global flags that belong to the top-level parser only
    _GLOBAL_FLAGS = {"-V", "--version", "-h", "--help",
                     "--list-profiles", "--list-metrics", "--show-schema"}

    result = list(argv)
    i = 0
    skip_next = False

    while i < len(result):
        tok = result[i]
        if skip_next:
            skip_next = False
            i += 1
            continue
        if tok.startswith("-"):
            if "=" not in tok and tok in _VALUE_FLAGS:
                skip_next = True
            i += 1
            continue
        # First non-flag token: check if it's a known subcommand
        if tok in _KNOWN_SUBCOMMANDS:
            # Already has a subcommand — no injection needed
            return result
        # Not a known subcommand → inject 'generate' at position 0
        return ["generate"] + result

    # No positional found at all (only flags) — inject 'generate' if not a
    # global-only invocation (those will be handled before _cmd_generate)
    # Check if any global-only flag is present; if so, don't inject
    for tok in result:
        if tok.split("=")[0] in _GLOBAL_FLAGS:
            return result
    return ["generate"] + result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    argv = _preprocess_argv(sys.argv[1:])
    parser = _build_parser()
    args = parser.parse_args(argv)

    config_dir: Optional[Path] = None
    if hasattr(args, "config_dir") and args.config_dir:
        config_dir = Path(args.config_dir)

    # Fleet stub
    if args.subcommand == "fleet":
        print("error: fleet subcommand not yet implemented", file=sys.stderr)
        sys.exit(2)

    # Informational commands (top-level flags, checked before subcommand)
    if getattr(args, "show_schema", False):
        sys.exit(_cmd_show_schema())

    if getattr(args, "list_metrics", False):
        sys.exit(_cmd_list_metrics())

    if getattr(args, "list_profiles", False):
        sys.exit(_cmd_list_profiles(config_dir))

    # Generate (default)
    sys.exit(_cmd_generate(args))

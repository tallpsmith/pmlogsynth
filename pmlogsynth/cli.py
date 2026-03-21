"""CLI entry point for pmlogsynth."""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from pmlogsynth import __version__
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
    "disk.dev.aveq",
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
    "hinv.ndisk",
    "hinv.ninterface",
    "hinv.pagesize",
    "hinv.physmem",
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
    "kernel.uname.distro",
    "kernel.uname.machine",
    "kernel.uname.nodename",
    "kernel.uname.release",
    "kernel.uname.sysname",
    "kernel.uname.version",
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
    "network.all.in.bytes",
    "network.all.in.errors",
    "network.all.in.packets",
    "network.all.out.bytes",
    "network.all.out.errors",
    "network.all.out.packets",
    "network.interface.in.bytes",
    "network.interface.in.errors",
    "network.interface.in.packets",
    "network.interface.out.bytes",
    "network.interface.out.errors",
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
        version="%(prog)s " + __version__,
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

    # --- fleet subcommand ---
    fleet_parser = subparsers.add_parser(
        "fleet",
        help="Generate a fleet of PCP archives from a fleet profile.",
        add_help=True,
    )
    _add_fleet_args(fleet_parser)

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


def _add_fleet_args(p: argparse.ArgumentParser) -> None:
    """Add fleet-command arguments to the fleet subparser."""
    p.add_argument(
        "fleet_profile",
        metavar="FLEET_PROFILE",
        help="Path to YAML fleet profile.",
    )
    p.add_argument(
        "-o", "--output-dir",
        metavar="PATH",
        dest="output_dir",
        help=(
            "Output directory for fleet archives "
            "(default: ./generated-archives/fleet-<name>)."
        ),
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic host assignment.",
    )
    p.add_argument(
        "--jobs",
        type=int,
        default=os.cpu_count() or 1,
        metavar="N",
        help="Parallel archive generation jobs (default: cpu count).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Print host assignments without generating archives.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing archive files without error.",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        default=False,
        help="Validate fleet profile only; do not generate any files.",
    )
    p.add_argument(
        "--start",
        metavar="TIMESTAMP",
        help=(
            "Archive start time (ISO 8601 or 'YYYY-MM-DD HH:MM:SS TZ'). "
            "Default: today at 00:00:00 UTC."
        ),
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Print per-host generation progress to stderr.",
    )
    p.add_argument(
        "-C", "--config-dir",
        metavar="PATH",
        dest="config_dir",
        help="Additional hardware profile directory (highest precedence).",
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


def _cmd_fleet(args: argparse.Namespace) -> int:
    """Handle the fleet subcommand."""
    config_dir = Path(args.config_dir) if args.config_dir else None

    # Validate flag incompatibilities
    if args.validate:
        for flag in ("force", "dry_run"):
            if getattr(args, flag, False):
                print(
                    "error: --validate is incompatible with "
                    "--{}".format(flag.replace("_", "-")),
                    file=sys.stderr,
                )
                return 1

    # Load fleet profile
    from pmlogsynth.fleet import (
        assign_hosts,
        check_override_warnings,
        generate_fleet,
        load_fleet_profile,
        print_dry_run,
    )

    try:
        fleet = load_fleet_profile(Path(args.fleet_profile))
    except ValidationError as exc:
        print("Validation error: {}".format(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print("Error reading fleet profile: {}".format(exc), file=sys.stderr)
        return 2

    # --validate mode
    if args.validate:
        check_override_warnings(fleet)
        print("fleet profile '{}' is valid".format(fleet.meta.name))
        return 0

    # --dry-run mode
    if args.dry_run:
        assignments = assign_hosts(fleet, seed=args.seed)
        print_dry_run(fleet, assignments, seed=args.seed)
        return 0

    # Full generation
    start_time = None
    if args.start:
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        try:
            start_time = parse_absolute_timestamp(args.start, field="--start")
        except ValidationError as exc:
            print("error: {}".format(exc), file=sys.stderr)
            return 1

    output_dir_str = args.output_dir
    if not output_dir_str:
        output_dir_str = str(
            Path("generated-archives") / "fleet-{}".format(fleet.meta.name)
        )
    output_dir = Path(output_dir_str)

    assignments = assign_hosts(fleet, seed=args.seed)

    try:
        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=output_dir,
            seed=args.seed,
            jobs=args.jobs,
            force=args.force,
            start=start_time,
            verbose=args.verbose,
            config_dir=config_dir,
        )
    except Exception as exc:
        print("error: Fleet generation failed: {}".format(exc), file=sys.stderr)
        return 3

    print("Fleet '{}': {} archives written to {}".format(
        fleet.meta.name, len(assignments), output_dir,
    ))
    return 0


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
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        try:
            start_time = parse_absolute_timestamp(args.start, field="--start")
        except ValidationError as exc:
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

    # Fleet subcommand
    if args.subcommand == "fleet":
        sys.exit(_cmd_fleet(args))

    # Informational commands (top-level flags, checked before subcommand)
    if getattr(args, "show_schema", False):
        sys.exit(_cmd_show_schema())

    if getattr(args, "list_metrics", False):
        sys.exit(_cmd_list_metrics())

    if getattr(args, "list_profiles", False):
        sys.exit(_cmd_list_profiles(config_dir))

    # Generate (default)
    sys.exit(_cmd_generate(args))

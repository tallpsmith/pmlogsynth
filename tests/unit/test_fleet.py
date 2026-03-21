"""Unit tests for fleet profile loading and host assignment."""

from pathlib import Path

import pytest

FLEET_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fleet"


class TestInlineProfile:
    """Tests for the InlineProfile dataclass."""

    def test_inline_profile_holds_phases_raw(self) -> None:
        from pmlogsynth.fleet.models import InlineProfile

        phases = [{"name": "steady", "duration": 600, "cpu": {"utilization": 0.5}}]
        profile = InlineProfile(phases=phases)
        assert profile.phases == phases

    def test_inline_profile_default_empty_phases(self) -> None:
        from pmlogsynth.fleet.models import InlineProfile

        profile = InlineProfile(phases=[])
        assert profile.phases == []


class TestLoadFleetProfile:
    """Tests for load_fleet_profile YAML parsing."""

    def test_loads_valid_fleet_profile(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assert fleet.meta.name == "test-fleet"
        assert fleet.meta.duration == 600
        assert fleet.meta.interval == 60
        assert fleet.meta.hostname_prefix == "host"
        assert fleet.meta.hardware == "generic-small"
        assert fleet.hosts.count == 5
        assert fleet.hosts.baseline == "baseline"
        assert fleet.hosts.jitter == 0.05
        assert fleet.bad_actors.count == 1
        assert fleet.bad_actors.jitter == 0.15
        assert len(fleet.bad_actors.profiles) == 1
        assert "baseline" in fleet.profiles
        assert "bad-cpu" in fleet.profiles

    def test_profiles_contain_phases(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assert len(fleet.profiles["baseline"].phases) == 1
        assert fleet.profiles["baseline"].phases[0]["name"] == "steady"
        assert len(fleet.profiles["bad-cpu"].phases) == 1
        assert fleet.profiles["bad-cpu"].phases[0]["name"] == "saturated"

    def test_missing_profiles_section_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_baseline_references_missing_profile_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: bar\n"
        )
        with pytest.raises(ValidationError, match="bar.*not found in profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actor_references_missing_profile_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 2\n  baseline: foo\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - missing\n"
        )
        with pytest.raises(ValidationError, match="missing.*not found in profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_meta_name_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="meta.name"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_hosts_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
        )
        with pytest.raises(ValidationError, match="hosts"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_count_exceeds_host_count_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 2\n  baseline: foo\n"
            "bad_actors:\n  count: 3\n  profiles:\n    - foo\n"
        )
        with pytest.raises(ValidationError, match="bad_actors.count"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_defaults_jitter_to_hosts_jitter(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: foo\n  jitter: 0.08\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.jitter == 0.08

    def test_no_bad_actors_section_is_valid(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.count == 0
        assert fleet.bad_actors.profiles == []

    def test_duration_accepts_duration_strings(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 24h\n  interval: 15s\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.meta.duration == 86400
        assert fleet.meta.interval == 15

    def test_profile_with_empty_phases_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases: []\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="phases.*non-empty"):
            load_fleet_profile(tmp_path / "bad.yaml")


class TestAssignHosts:
    """Tests for host assignment with random bad-actor selection."""

    def test_correct_total_count(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        assert len(assignments) == 5

    def test_correct_bad_actor_count(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        bad = [a for a in assignments if a.role == "bad_actor"]
        assert len(bad) == 1

    def test_hostnames_zero_padded(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        hostnames = [a.hostname for a in assignments]
        assert hostnames == ["host-01", "host-02", "host-03", "host-04", "host-05"]

    def test_seed_produces_deterministic_assignments(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        a1 = assign_hosts(fleet, seed=42)
        a2 = assign_hosts(fleet, seed=42)
        assert [a.hostname for a in a1 if a.role == "bad_actor"] == \
               [a.hostname for a in a2 if a.role == "bad_actor"]
        assert [a.jitter_factor for a in a1] == [a.jitter_factor for a in a2]

    def test_different_seeds_produce_different_assignments(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        a1 = assign_hosts(fleet, seed=42)
        a2 = assign_hosts(fleet, seed=99)
        factors1 = [a.jitter_factor for a in a1]
        factors2 = [a.jitter_factor for a in a2]
        assert factors1 != factors2

    def test_bad_actor_gets_bad_actor_jitter_stddev(self) -> None:
        """Bad actor jitter factors should use bad_actors.jitter, not hosts.jitter."""
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        import statistics

        bad_factors = []
        baseline_factors = []
        for seed in range(100):
            assignments = assign_hosts(fleet, seed=seed)
            for a in assignments:
                if a.role == "bad_actor":
                    bad_factors.append(a.jitter_factor)
                else:
                    baseline_factors.append(a.jitter_factor)

        bad_std = statistics.stdev(bad_factors)
        baseline_std = statistics.stdev(baseline_factors)
        assert bad_std > baseline_std * 1.5

    def test_no_bad_actors_all_baseline(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "profiles:\n  base:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: base\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert all(a.role == "baseline" for a in assignments)

    def test_none_seed_produces_assignments(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=None)
        assert len(assignments) == 5

    def test_zero_pad_width_scales_with_count(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "profiles:\n  base:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 100\n  baseline: base\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert assignments[0].hostname == "srv-001"
        assert assignments[99].hostname == "srv-100"

    def test_bad_actor_profiles_selected_from_pool(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        bad = [a for a in assignments if a.role == "bad_actor"]
        for b in bad:
            assert b.workload_rel in ("bad-cpu",)


class TestWriteManifest:
    """Tests for fleet.manifest YAML output."""

    def test_manifest_contains_all_hosts(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts,
            load_fleet_profile,
            write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        manifest_path = tmp_path / "fleet.manifest"
        write_manifest(manifest_path, fleet, assignments, seed=42)

        import yaml as _yaml

        manifest = _yaml.safe_load(manifest_path.read_text())
        assert manifest["meta"]["name"] == "test-fleet"
        assert manifest["meta"]["host_count"] == 5
        assert manifest["meta"]["seed"] == 42
        assert len(manifest["archives"]) == 5

    def test_manifest_roles_match_assignments(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts,
            load_fleet_profile,
            write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        write_manifest(tmp_path / "fleet.manifest", fleet, assignments, seed=42)

        import yaml as _yaml

        manifest = _yaml.safe_load((tmp_path / "fleet.manifest").read_text())
        for entry, assignment in zip(manifest["archives"], assignments):
            assert entry["hostname"] == assignment.hostname
            assert entry["role"] == assignment.role
            assert entry["jitter_factor"] == pytest.approx(assignment.jitter_factor)

    def test_manifest_records_none_seed(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts,
            load_fleet_profile,
            write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=None)
        write_manifest(tmp_path / "fleet.manifest", fleet, assignments, seed=None)

        import yaml as _yaml

        manifest = _yaml.safe_load((tmp_path / "fleet.manifest").read_text())
        assert manifest["meta"]["seed"] is None


class TestOverrideWarnings:
    """Tests for warnings when fleet settings override workload profile values."""

    def test_warns_on_duration_conflict(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from pmlogsynth.fleet import check_override_warnings, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        from dataclasses import replace

        fleet_different = replace(fleet, meta=replace(fleet.meta, duration=3600))
        with caplog.at_level(logging.WARNING):
            check_override_warnings(fleet_different)
        assert any("duration" in r.message for r in caplog.records)

    def test_no_warning_when_values_match(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from pmlogsynth.fleet import check_override_warnings, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        with caplog.at_level(logging.WARNING):
            check_override_warnings(fleet)
        assert not any("duration" in r.message for r in caplog.records)


class TestDryRun:
    """Tests for --dry-run output formatting."""

    def test_dry_run_prints_all_hosts(self, capsys: pytest.CaptureFixture) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile, print_dry_run

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        print_dry_run(fleet, assignments, seed=42)

        captured = capsys.readouterr()
        assert "test-fleet" in captured.out
        assert "5 hosts" in captured.out
        for a in assignments:
            assert a.hostname in captured.out
        bad = [a for a in assignments if a.role == "bad_actor"]
        for b in bad:
            assert "BAD" in captured.out

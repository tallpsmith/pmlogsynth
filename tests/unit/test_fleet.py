"""Unit tests for fleet profile loading and host assignment."""

from pathlib import Path

import pytest

FLEET_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fleet"


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
        assert fleet.hosts.jitter == 0.05
        assert fleet.bad_actors.count == 1
        assert fleet.bad_actors.jitter == 0.15
        assert len(fleet.bad_actors.profiles) == 1

    def test_missing_meta_name_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: x.yaml\n"
        )
        with pytest.raises(ValidationError, match="meta.name"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_hosts_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
        )
        with pytest.raises(ValidationError, match="hosts"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_count_exceeds_host_count_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 2\n  baseline: x.yaml\n"
            "bad_actors:\n  count: 3\n  profiles:\n    - y.yaml\n"
        )
        with pytest.raises(ValidationError, match="bad_actors.count"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_defaults_jitter_to_hosts_jitter(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 3\n  baseline: x.yaml\n  jitter: 0.08\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - y.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.jitter == 0.08

    def test_no_bad_actors_section_is_valid(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 3\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.count == 0
        assert fleet.bad_actors.profiles == []

    def test_duration_accepts_duration_strings(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 24h\n  interval: 15s\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.meta.duration == 86400
        assert fleet.meta.interval == 15

    def test_workload_paths_resolved_relative_to_fleet_file(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assert fleet.hosts.baseline_path.exists()
        assert fleet.hosts.baseline_path.name == "baseline.yaml"


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
            "hosts:\n  count: 3\n  baseline: x.yaml\n"
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
            "hosts:\n  count: 100\n  baseline: x.yaml\n"
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
            assert b.workload_path.name in ("bad-cpu.yaml",)

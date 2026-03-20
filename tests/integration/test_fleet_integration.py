"""Integration tests for fleet generation with mocked PCP."""

from pathlib import Path
from unittest.mock import MagicMock, patch

FLEET_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fleet"


class TestGenerateFleet:
    """Tests for the fleet generation orchestrator."""

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_generates_correct_number_of_archives(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import assign_hosts, generate_fleet, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        assert mock_writer_cls.call_count == 5

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_manifest_written_after_generation(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import assign_hosts, generate_fleet, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_mod.ArchiveWriter = MagicMock()
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        assert (tmp_path / "fleet.manifest").exists()

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_fleet_overrides_applied_to_profiles(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import assign_hosts, generate_fleet, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        for call_args, assignment in zip(mock_writer_cls.call_args_list, assignments):
            # ArchiveWriter is called with keyword args
            profile = call_args[1]["profile"] if "profile" in call_args[1] else call_args[0][1]
            assert profile.meta.hostname == assignment.hostname
            assert profile.meta.duration == fleet.meta.duration
            assert profile.meta.interval == fleet.meta.interval

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_output_directory_created(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import assign_hosts, generate_fleet, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_mod.ArchiveWriter = MagicMock()
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        out = tmp_path / "nested" / "output"

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=out,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        assert out.exists()

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_parallel_jobs_generates_all_archives(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import assign_hosts, generate_fleet, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=2,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        assert mock_writer_cls.call_count == 5
        assert (tmp_path / "fleet.manifest").exists()

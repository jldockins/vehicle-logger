"""Tests for sync.py — all network and filesystem operations mocked."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config
import sync


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path, monkeypatch):
    """Redirect storage to temp directory for every test."""
    monkeypatch.setattr(config, "TRIPS_DIR", tmp_path / "trips")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "CAR_ID", "test-car")
    monkeypatch.setattr(config, "SERVER_HOST", "192.168.1.100")
    monkeypatch.setattr(config, "SERVER_USER", "pi")
    monkeypatch.setattr(config, "SERVER_SYNC_PATH", "/mnt/user/vehicle-logs")
    monkeypatch.setattr(config, "HOME_SSID", "TestWiFi")
    # Update MANIFEST_PATH since TRIPS_DIR changed
    monkeypatch.setattr(sync, "MANIFEST_PATH", tmp_path / "trips" / ".synced.json")


@pytest.fixture()
def trip_files(tmp_path):
    """Create some fake trip database files."""
    car_dir = tmp_path / "trips" / "test-car"
    car_dir.mkdir(parents=True)
    files = []
    for name in ["20260407-1200.db", "20260407-1400.db", "20260407-1600.db"]:
        f = car_dir / name
        f.write_text("fake sqlite data")
        files.append(f)
    return files


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
class TestManifest:
    def test_load_empty_manifest(self):
        assert sync.load_manifest() == set()

    def test_save_and_load_manifest(self, tmp_path):
        synced = {"test-car/20260407-1200.db", "test-car/20260407-1400.db"}
        sync.save_manifest(synced)

        loaded = sync.load_manifest()
        assert loaded == synced

    def test_corrupt_manifest_returns_empty(self, tmp_path):
        sync.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        sync.MANIFEST_PATH.write_text("not json{{{")

        assert sync.load_manifest() == set()


# ---------------------------------------------------------------------------
# WiFi check
# ---------------------------------------------------------------------------
class TestIsOnHomeWifi:
    @patch("sync.subprocess.run")
    def test_on_home_wifi(self, mock_run):
        mock_run.return_value = MagicMock(stdout="TestWiFi\n")

        assert sync.is_on_home_wifi() is True

    @patch("sync.subprocess.run")
    def test_on_different_wifi(self, mock_run):
        mock_run.return_value = MagicMock(stdout="Starbucks\n")

        assert sync.is_on_home_wifi() is False

    @patch("sync.subprocess.run")
    def test_no_wifi_connection(self, mock_run):
        mock_run.return_value = MagicMock(stdout="\n")

        assert sync.is_on_home_wifi() is False

    def test_no_ssid_configured(self, monkeypatch):
        monkeypatch.setattr(config, "HOME_SSID", "")

        assert sync.is_on_home_wifi() is False

    @patch("sync.subprocess.run", side_effect=FileNotFoundError)
    def test_iwgetid_not_found(self, mock_run):
        assert sync.is_on_home_wifi() is False


# ---------------------------------------------------------------------------
# Find unsynced trips
# ---------------------------------------------------------------------------
class TestFindUnsyncedTrips:
    def test_all_unsynced(self, trip_files):
        unsynced = sync.find_unsynced_trips()
        assert len(unsynced) == 3

    def test_some_already_synced(self, trip_files):
        sync.save_manifest({"test-car/20260407-1200.db"})

        unsynced = sync.find_unsynced_trips()
        assert len(unsynced) == 2
        names = [f.name for f in unsynced]
        assert "20260407-1200.db" not in names

    def test_all_synced(self, trip_files):
        sync.save_manifest({
            "test-car/20260407-1200.db",
            "test-car/20260407-1400.db",
            "test-car/20260407-1600.db",
        })

        assert sync.find_unsynced_trips() == []

    def test_no_trips_dir(self):
        assert sync.find_unsynced_trips() == []


# ---------------------------------------------------------------------------
# Rsync file
# ---------------------------------------------------------------------------
class TestRsyncFile:
    @patch("sync.subprocess.run")
    def test_successful_rsync(self, mock_run, trip_files):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        assert sync.rsync_file(trip_files[0]) is True

    @patch("sync.subprocess.run")
    def test_rsync_failure(self, mock_run, trip_files):
        # First call (ssh mkdir) succeeds, second call (rsync) fails
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="connection refused"),
        ]

        assert sync.rsync_file(trip_files[0]) is False

    @patch("sync.subprocess.run", side_effect=FileNotFoundError)
    def test_rsync_not_installed(self, mock_run, trip_files):
        assert sync.rsync_file(trip_files[0]) is False


# ---------------------------------------------------------------------------
# Full sync cycle
# ---------------------------------------------------------------------------
class TestSync:
    @patch("sync.rsync_file", return_value=True)
    def test_syncs_all_unsynced(self, mock_rsync, trip_files):
        count = sync.sync()

        assert count == 3
        assert mock_rsync.call_count == 3

        # Manifest should now have all 3
        manifest = sync.load_manifest()
        assert len(manifest) == 3

    @patch("sync.rsync_file", return_value=False)
    def test_failed_sync_not_in_manifest(self, mock_rsync, trip_files):
        count = sync.sync()

        assert count == 0
        assert sync.load_manifest() == set()

    @patch("sync.rsync_file", return_value=True)
    def test_no_trips_to_sync(self, mock_rsync):
        count = sync.sync()

        assert count == 0
        mock_rsync.assert_not_called()

    def test_no_server_configured(self, monkeypatch, trip_files):
        monkeypatch.setattr(config, "SERVER_HOST", "")

        assert sync.sync() == 0

"""Tests for server/ingest.py — InfluxDB is mocked."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock influxdb_client before importing ingest
import sys
from unittest.mock import MagicMock

influx_mock = MagicMock()
sys.modules["influxdb_client"] = influx_mock
sys.modules["influxdb_client.client"] = MagicMock()
sys.modules["influxdb_client.client.write_api"] = MagicMock()

# Provide real Point-like behavior for parsing tests
class FakePoint:
    def __init__(self, measurement):
        self._measurement = measurement
        self._tags = {}
        self._fields = {}
        self._time = None

    def tag(self, key, value):
        self._tags[key] = value
        return self

    def field(self, key, value):
        self._fields[key] = value
        return self

    def time(self, ts, precision):
        self._time = ts
        return self

influx_mock.Point = FakePoint
influx_mock.WritePrecision.S = "s"

# Now we can import
from fastapi.testclient import TestClient

from server.ingest import (
    app,
    find_new_trips,
    ingest_file,
    load_ingested,
    parse_trip_dtcs,
    parse_trip_log,
    save_ingested,
)
import server.ingest as ingest_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path, monkeypatch):
    """Redirect watch dir and manifest to temp directory."""
    watch_dir = tmp_path / "vehicle-logs"
    watch_dir.mkdir()
    monkeypatch.setattr(ingest_module, "WATCH_DIR", watch_dir)
    monkeypatch.setattr(ingest_module, "INGESTED_MANIFEST", watch_dir / ".ingested.json")


@pytest.fixture()
def sample_trip_db(tmp_path) -> Path:
    """Create a sample trip SQLite database with test data."""
    watch_dir = tmp_path / "vehicle-logs"
    car_dir = watch_dir / "test-car"
    car_dir.mkdir(parents=True, exist_ok=True)
    db_path = car_dir / "20260407-1200.db"

    schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    schema_sql = schema_path.read_text()

    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema_sql)

    # Insert sample log rows
    conn.execute(
        "INSERT INTO log (timestamp, car_id, trip_id, speed_obd, rpm, "
        "engine_load, coolant_temp, throttle_pos, fuel_trim_short, "
        "fuel_trim_long, intake_temp, intake_pressure, timing_advance, "
        "fuel_level, lat, lon, speed_gps, heading, altitude, gps_fix) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2026-04-07T12:00:01Z", "test-car", "20260407-1200",
            45.0, 1850.0, 32.5, 195.0, 18.2, 1.5, -0.8,
            72.0, 101.3, 12.0, 68.0,
            42.9956, -71.4548, 44.8, 182.3, 213.0, 3,
        ),
    )
    conn.execute(
        "INSERT INTO log (timestamp, car_id, trip_id, speed_obd, rpm, "
        "engine_load, coolant_temp, throttle_pos, fuel_trim_short, "
        "fuel_trim_long, intake_temp, intake_pressure, timing_advance, "
        "fuel_level, lat, lon, speed_gps, heading, altitude, gps_fix) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2026-04-07T12:00:02Z", "test-car", "20260407-1200",
            50.0, 2000.0, 35.0, 196.0, 20.0, 1.2, -0.5,
            73.0, 102.0, 13.0, 67.5,
            42.9960, -71.4550, 49.5, 180.0, 214.0, 3,
        ),
    )

    # Insert a DTC
    conn.execute(
        "INSERT INTO dtcs (timestamp, car_id, trip_id, code, description) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-04-07T12:00:01Z", "test-car", "20260407-1200", "P0301", "Cylinder 1 Misfire"),
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
class TestManifest:
    def test_load_empty(self):
        assert load_ingested() == set()

    def test_save_and_load(self):
        save_ingested({"test-car/trip1.db", "test-car/trip2.db"})
        assert load_ingested() == {"test-car/trip1.db", "test-car/trip2.db"}

    def test_corrupt_manifest(self):
        ingest_module.INGESTED_MANIFEST.write_text("bad json{{{")
        assert load_ingested() == set()


# ---------------------------------------------------------------------------
# Parse trip log
# ---------------------------------------------------------------------------
class TestParseTripLog:
    def test_parses_log_rows(self, sample_trip_db):
        points = parse_trip_log(sample_trip_db)

        assert len(points) == 2
        assert points[0]._measurement == "vehicle_data"
        assert points[0]._tags["car_id"] == "test-car"
        assert points[0]._tags["trip_id"] == "20260407-1200"
        assert points[0]._fields["speed_obd"] == 45.0
        assert points[0]._fields["rpm"] == 1850.0
        assert points[0]._fields["lat"] == 42.9956
        assert points[0]._time == "2026-04-07T12:00:01Z"

    def test_skips_null_fields(self, tmp_path):
        """Rows with NULL values should not include those fields."""
        watch_dir = tmp_path / "vehicle-logs"
        car_dir = watch_dir / "test-car"
        car_dir.mkdir(parents=True, exist_ok=True)
        db_path = car_dir / "sparse.db"

        schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(schema_path.read_text())
        conn.execute(
            "INSERT INTO log (timestamp, car_id, trip_id, speed_obd, rpm) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2026-04-07T12:00:01Z", "test-car", "20260407-1200", 45.0, None),
        )
        conn.commit()
        conn.close()

        points = parse_trip_log(db_path)
        assert len(points) == 1
        assert "speed_obd" in points[0]._fields
        assert "rpm" not in points[0]._fields


# ---------------------------------------------------------------------------
# Parse trip DTCs
# ---------------------------------------------------------------------------
class TestParseTripDTCs:
    def test_parses_dtc_rows(self, sample_trip_db):
        points = parse_trip_dtcs(sample_trip_db)

        assert len(points) == 1
        assert points[0]._measurement == "vehicle_dtc"
        assert points[0]._tags["code"] == "P0301"
        assert points[0]._fields["description"] == "Cylinder 1 Misfire"


# ---------------------------------------------------------------------------
# Find new trips
# ---------------------------------------------------------------------------
class TestFindNewTrips:
    def test_finds_unprocessed(self, sample_trip_db):
        new = find_new_trips()
        assert len(new) == 1

    def test_skips_ingested(self, sample_trip_db):
        save_ingested({"test-car/20260407-1200.db"})
        assert find_new_trips() == []

    def test_no_watch_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ingest_module, "WATCH_DIR", tmp_path / "nonexistent")
        assert find_new_trips() == []


# ---------------------------------------------------------------------------
# Ingest file
# ---------------------------------------------------------------------------
class TestIngestFile:
    def test_writes_points(self, sample_trip_db):
        mock_write_api = MagicMock()

        count = ingest_file(sample_trip_db, mock_write_api)

        assert count == 3  # 2 log rows + 1 DTC
        mock_write_api.write.assert_called_once()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
class TestAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_status_empty(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending"] == 0
        assert data["ingested"] == 0

    def test_status_with_pending(self, client, sample_trip_db):
        resp = client.get("/status")
        data = resp.json()
        assert data["pending"] == 1

    @patch("server.ingest.run_ingest", return_value={"files": 1, "points": 3})
    def test_trigger_ingest(self, mock_run, client):
        resp = client.post("/ingest")
        assert resp.status_code == 200
        assert resp.json() == {"files": 1, "points": 3}

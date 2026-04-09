"""Tests for logger.py — all hardware is mocked."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config
import logger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path, monkeypatch):
    """Redirect trip and log storage to a temp directory for every test."""
    monkeypatch.setattr(config, "TRIPS_DIR", tmp_path / "trips")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "CAR_ID", "test-car")


@pytest.fixture()
def trip_db(tmp_path) -> sqlite3.Connection:
    """Create a trip database using the real schema."""
    return logger.create_trip_db("20260407-1200")


# ---------------------------------------------------------------------------
# OBD polling
# ---------------------------------------------------------------------------
class TestPollOBD:
    def test_returns_values_for_all_pids(self):
        mock_conn = MagicMock()

        def make_response(value):
            resp = MagicMock()
            resp.is_null.return_value = False
            resp.value.magnitude = value
            return resp

        responses = {
            "SPEED": make_response(45.0),
            "RPM": make_response(1850.0),
            "ENGINE_LOAD": make_response(32.5),
            "COOLANT_TEMP": make_response(195.0),
            "THROTTLE_POS": make_response(18.2),
            "SHORT_FUEL_TRIM_1": make_response(1.5),
            "LONG_FUEL_TRIM_1": make_response(-0.8),
            "INTAKE_TEMP": make_response(72.0),
            "INTAKE_PRESSURE": make_response(101.3),
            "TIMING_ADVANCE": make_response(12.0),
            "FUEL_LEVEL": make_response(68.0),
        }

        # Make obd.commands[pid] return an object whose query returns the response
        mock_commands = {}
        for pid, resp in responses.items():
            cmd = MagicMock()
            cmd.name = pid
            mock_commands[pid] = cmd

        logger.obd.commands.__getitem__ = lambda self, key: mock_commands[key]
        mock_conn.query.side_effect = lambda cmd: responses[cmd.name]

        data = logger.poll_obd(mock_conn)

        assert data["speed_obd"] == 45.0
        assert data["rpm"] == 1850.0
        assert data["engine_load"] == 32.5
        assert data["coolant_temp"] == 195.0
        assert data["fuel_level"] == 68.0
        assert len(data) == len(config.OBD_PIDS)

    def test_null_response_returns_none(self):
        mock_conn = MagicMock()
        resp = MagicMock()
        resp.is_null.return_value = True
        mock_conn.query.return_value = resp

        data = logger.poll_obd(mock_conn)

        assert all(v is None for v in data.values())

    def test_exception_returns_none(self):
        mock_conn = MagicMock()
        mock_conn.query.side_effect = Exception("Bluetooth lost")

        data = logger.poll_obd(mock_conn)

        assert all(v is None for v in data.values())


# ---------------------------------------------------------------------------
# DTC polling
# ---------------------------------------------------------------------------
class TestPollDTCs:
    def test_returns_dtc_list(self):
        mock_conn = MagicMock()
        resp = MagicMock()
        resp.is_null.return_value = False
        resp.value = [("P0301", "Cylinder 1 Misfire"), ("P0420", "Catalyst Efficiency")]
        mock_conn.query.return_value = resp

        dtcs = logger.poll_dtcs(mock_conn)

        assert len(dtcs) == 2
        assert dtcs[0] == ("P0301", "Cylinder 1 Misfire")

    def test_no_dtcs_returns_empty(self):
        mock_conn = MagicMock()
        resp = MagicMock()
        resp.is_null.return_value = True
        mock_conn.query.return_value = resp

        assert logger.poll_dtcs(mock_conn) == []

    def test_exception_returns_empty(self):
        mock_conn = MagicMock()
        mock_conn.query.side_effect = Exception("OBD error")

        assert logger.poll_dtcs(mock_conn) == []


# ---------------------------------------------------------------------------
# GPS polling
# ---------------------------------------------------------------------------
class TestPollGPS:
    def test_parses_tpv_report(self):
        mock_session = MagicMock()
        report = MagicMock()
        report.get.side_effect = lambda k: "TPV" if k == "class" else None
        report.mode = 3
        report.lat = 42.9956
        report.lon = -71.4548
        report.speed = 20.0  # m/s
        report.track = 182.3
        report.alt = 213.0
        mock_session.waiting.side_effect = [True, False]
        mock_session.next.return_value = report

        data = logger.poll_gps(mock_session)

        assert data["gps_fix"] == 3
        assert data["lat"] == 42.9956
        assert data["lon"] == -71.4548
        assert data["speed_gps"] == pytest.approx(20.0 * 2.23694, rel=1e-3)
        assert data["heading"] == 182.3
        assert data["altitude"] == 213.0

    def test_no_fix_returns_defaults(self):
        mock_session = MagicMock()
        report = MagicMock()
        report.get.side_effect = lambda k: "TPV" if k == "class" else None
        report.mode = 0
        mock_session.waiting.side_effect = [True, False]
        mock_session.next.return_value = report

        # Need to make getattr return None for position fields
        del report.lat
        del report.lon
        del report.speed
        del report.track
        del report.alt

        data = logger.poll_gps(mock_session)

        assert data["gps_fix"] == 0
        assert data["lat"] is None
        assert data["lon"] is None

    def test_no_waiting_data_returns_defaults(self):
        mock_session = MagicMock()
        mock_session.waiting.return_value = False

        data = logger.poll_gps(mock_session)

        assert data["gps_fix"] == 0
        assert data["lat"] is None

    def test_stop_iteration_returns_defaults(self):
        mock_session = MagicMock()
        mock_session.waiting.return_value = True
        mock_session.next.side_effect = StopIteration

        data = logger.poll_gps(mock_session)

        assert data["gps_fix"] == 0
        assert data["lat"] is None


# ---------------------------------------------------------------------------
# Trip database
# ---------------------------------------------------------------------------
class TestTripDB:
    def test_creates_db_file(self):
        conn = logger.create_trip_db("20260407-1200")
        db_path = config.TRIPS_DIR / "test-car" / "20260407-1200.db"
        assert db_path.exists()
        conn.close()

    def test_schema_has_log_table(self, trip_db):
        cursor = trip_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='log'"
        )
        assert cursor.fetchone() is not None

    def test_schema_has_dtcs_table(self, trip_db):
        cursor = trip_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dtcs'"
        )
        assert cursor.fetchone() is not None

    def test_wal_mode_enabled(self, trip_db):
        cursor = trip_db.execute("PRAGMA journal_mode")
        assert cursor.fetchone()[0] == "wal"


# ---------------------------------------------------------------------------
# Write record
# ---------------------------------------------------------------------------
class TestWriteRecord:
    def test_inserts_row(self, trip_db):
        obd_data = {
            "speed_obd": 45.0, "rpm": 1850.0, "engine_load": 32.5,
            "coolant_temp": 195.0, "throttle_pos": 18.2,
            "fuel_trim_short": 1.5, "fuel_trim_long": -0.8,
            "intake_temp": 72.0, "intake_pressure": 101.3,
            "timing_advance": 12.0, "fuel_level": 68.0,
        }
        gps_data = {
            "lat": 42.9956, "lon": -71.4548, "speed_gps": 44.8,
            "heading": 182.3, "altitude": 213.0, "gps_fix": 3,
        }

        logger.write_record(trip_db, "20260407-1200", obd_data, gps_data)

        rows = trip_db.execute("SELECT * FROM log").fetchall()
        assert len(rows) == 1

    def test_handles_null_values(self, trip_db):
        obd_data = {k: None for k in logger.PID_TO_COLUMN.values()}
        gps_data = {
            "lat": None, "lon": None, "speed_gps": None,
            "heading": None, "altitude": None, "gps_fix": 0,
        }

        logger.write_record(trip_db, "20260407-1200", obd_data, gps_data)

        rows = trip_db.execute("SELECT * FROM log").fetchall()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Write DTCs
# ---------------------------------------------------------------------------
class TestWriteDTCs:
    def test_inserts_dtcs(self, trip_db):
        dtcs = [("P0301", "Cylinder 1 Misfire"), ("P0420", "Catalyst Efficiency")]

        logger.write_dtcs(trip_db, "20260407-1200", dtcs)

        rows = trip_db.execute("SELECT code, description FROM dtcs").fetchall()
        assert len(rows) == 2
        assert rows[0] == ("P0301", "Cylinder 1 Misfire")

    def test_empty_dtcs_writes_nothing(self, trip_db):
        logger.write_dtcs(trip_db, "20260407-1200", [])

        rows = trip_db.execute("SELECT * FROM dtcs").fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Trip detection
# ---------------------------------------------------------------------------
class TestTripDetection:
    def test_engine_running_with_rpm(self):
        assert logger.is_engine_running({"rpm": 800.0}) is True

    def test_engine_not_running_rpm_zero(self):
        assert logger.is_engine_running({"rpm": 0.0}) is False

    def test_engine_not_running_rpm_none(self):
        assert logger.is_engine_running({"rpm": None}) is False

    def test_engine_not_running_no_rpm_key(self):
        assert logger.is_engine_running({}) is False

    def test_trip_id_format(self):
        trip_id = logger.generate_trip_id()
        # Format: YYYYMMDD-HHMM
        assert len(trip_id) == 13
        assert trip_id[8] == "-"


# ---------------------------------------------------------------------------
# OBD connection
# ---------------------------------------------------------------------------
class TestConnectOBD:
    @patch("logger.obd.OBD")
    def test_successful_connection(self, mock_obd_class):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_obd_class.return_value = mock_conn

        result = logger.connect_obd()

        assert result is mock_conn
        mock_obd_class.assert_called_once_with(config.RFCOMM_PORT)

    @patch("logger.obd.OBD")
    def test_failed_connection_returns_none(self, mock_obd_class):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        mock_obd_class.return_value = mock_conn

        result = logger.connect_obd()

        assert result is None
        mock_conn.close.assert_called_once()

    @patch("logger.obd.OBD")
    def test_exception_returns_none(self, mock_obd_class):
        mock_obd_class.side_effect = Exception("No Bluetooth")

        assert logger.connect_obd() is None

"""Main OBD-II + GPS polling loop.

Connects to the Vgate iCar Pro over Bluetooth rfcomm and to gpsd for GPS.
Polls at ~1 Hz, merges data into timestamped records, and writes to a
per-trip SQLite database.

Designed to run as a systemd service on a Raspberry Pi Zero 2W.
"""

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import obd
from gps import gps, WATCH_ENABLE, WATCH_NEWSTYLE

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "logger.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Map python-obd command names → SQLite column names
# ---------------------------------------------------------------------------
PID_TO_COLUMN: dict[str, str] = {
    "SPEED": "speed_obd",
    "RPM": "rpm",
    "ENGINE_LOAD": "engine_load",
    "COOLANT_TEMP": "coolant_temp",
    "THROTTLE_POS": "throttle_pos",
    "SHORT_FUEL_TRIM_1": "fuel_trim_short",
    "LONG_FUEL_TRIM_1": "fuel_trim_long",
    "INTAKE_TEMP": "intake_temp",
    "INTAKE_PRESSURE": "intake_pressure",
    "TIMING_ADVANCE": "timing_advance",
    "FUEL_LEVEL": "fuel_level",
}


# ---------------------------------------------------------------------------
# OBD connection
# ---------------------------------------------------------------------------
def connect_obd() -> obd.OBD | None:
    """Attempt to connect to the OBD-II adapter over rfcomm."""
    try:
        connection = obd.OBD(config.RFCOMM_PORT)
        if connection.is_connected():
            log.info("OBD connected on %s", config.RFCOMM_PORT)
            return connection
        log.warning("OBD adapter found but not connected")
        connection.close()
    except Exception:
        log.exception("Failed to connect to OBD adapter")
    return None


def poll_obd(connection: obd.OBD) -> dict[str, float | None]:
    """Poll all configured PIDs and return a dict of column→value."""
    data: dict[str, float | None] = {}
    for pid in config.OBD_PIDS:
        column = PID_TO_COLUMN.get(pid)
        if column is None:
            continue
        try:
            response = connection.query(obd.commands[pid])
            data[column] = response.value.magnitude if not response.is_null() else None
        except Exception:
            log.exception("Error polling PID %s", pid)
            data[column] = None
    return data


def poll_dtcs(connection: obd.OBD) -> list[tuple[str, str]]:
    """Poll active DTCs. Returns list of (code, description) tuples."""
    try:
        response = connection.query(obd.commands.GET_DTC)
        if not response.is_null():
            return [(code, desc) for code, desc in response.value]
    except Exception:
        log.exception("Error polling DTCs")
    return []


# ---------------------------------------------------------------------------
# GPS connection
# ---------------------------------------------------------------------------
def connect_gps() -> gps | None:
    """Connect to the local gpsd daemon."""
    try:
        session = gps(mode=WATCH_ENABLE | WATCH_NEWSTYLE)
        log.info("GPS connected via gpsd")
        return session
    except Exception:
        log.exception("Failed to connect to gpsd")
    return None


def poll_gps(session: gps) -> dict[str, float | int | None]:
    """Read the latest GPS fix from gpsd.

    Drains all pending messages and returns data from the most recent TPV
    report, so the main loop never blocks waiting for GPS.
    """
    data: dict[str, float | int | None] = {
        "lat": None,
        "lon": None,
        "speed_gps": None,
        "heading": None,
        "altitude": None,
        "gps_fix": 0,
    }
    try:
        # Read all pending messages, keep the latest TPV
        while session.waiting():
            report = session.next()
            if report.get("class") != "TPV":
                continue
            fix = getattr(report, "mode", 0)
            data["gps_fix"] = fix
            if fix >= 2:
                data["lat"] = getattr(report, "lat", None)
                data["lon"] = getattr(report, "lon", None)
                # gpsd reports speed in m/s — convert to km/h
                speed_ms = getattr(report, "speed", None)
                if speed_ms is not None:
                    data["speed_gps"] = speed_ms * 3.6
                data["heading"] = getattr(report, "track", None)
            if fix >= 3:
                data["altitude"] = getattr(report, "alt", None)
    except StopIteration:
        log.debug("No GPS data available yet")
    except Exception:
        log.exception("Error reading GPS")
    return data


# ---------------------------------------------------------------------------
# Trip database management
# ---------------------------------------------------------------------------
def create_trip_db(trip_id: str) -> sqlite3.Connection:
    """Create a new per-trip SQLite database and return the connection."""
    trip_dir = config.TRIPS_DIR / config.CAR_ID
    trip_dir.mkdir(parents=True, exist_ok=True)
    db_path = trip_dir / f"{trip_id}.db"

    schema_path = Path(__file__).resolve().parent / "db" / "schema.sql"
    schema_sql = schema_path.read_text()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(schema_sql)
    conn.commit()
    log.info("Created trip database: %s", db_path)
    return conn


def write_record(
    conn: sqlite3.Connection,
    trip_id: str,
    obd_data: dict[str, float | None],
    gps_data: dict[str, float | int | None],
) -> None:
    """Write a single merged OBD+GPS record to the trip database."""
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "timestamp": now,
        "car_id": config.CAR_ID,
        "trip_id": trip_id,
        **obd_data,
        **gps_data,
    }
    columns = ", ".join(record.keys())
    placeholders = ", ".join("?" for _ in record)
    conn.execute(
        f"INSERT INTO log ({columns}) VALUES ({placeholders})",
        list(record.values()),
    )
    conn.commit()


def write_dtcs(
    conn: sqlite3.Connection,
    trip_id: str,
    dtcs: list[tuple[str, str]],
) -> None:
    """Write any new DTCs to the dtcs table."""
    now = datetime.now(timezone.utc).isoformat()
    for code, description in dtcs:
        conn.execute(
            "INSERT INTO dtcs (timestamp, car_id, trip_id, code, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (now, config.CAR_ID, trip_id, code, description),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Trip detection
# ---------------------------------------------------------------------------
def generate_trip_id() -> str:
    """Generate a trip ID from the current UTC time: YYYYMMDD-HHMM."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")


def is_engine_running(obd_data: dict[str, float | None]) -> bool:
    """Heuristic: engine is running if RPM is reported and > 0."""
    rpm = obd_data.get("rpm")
    return rpm is not None and rpm > 0


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("Vehicle logger starting — car_id=%s", config.CAR_ID)

    # Connect to hardware (retries on failure)
    obd_conn: obd.OBD | None = None
    gps_session: gps | None = None

    trip_id: str | None = None
    trip_db: sqlite3.Connection | None = None
    last_engine_time: float = 0.0
    poll_interval = 1.0 / config.POLL_RATE_HZ

    while True:
        loop_start = time.monotonic()

        # --- Ensure OBD connection ---
        if obd_conn is None or not obd_conn.is_connected():
            obd_conn = connect_obd()
            if obd_conn is None:
                log.info("OBD not available, retrying in 5s")
                time.sleep(5)
                continue

        # --- Ensure GPS connection ---
        if gps_session is None:
            gps_session = connect_gps()

        # --- Poll sensors ---
        obd_data = poll_obd(obd_conn)
        gps_data = poll_gps(gps_session) if gps_session else {
            "lat": None, "lon": None, "speed_gps": None,
            "heading": None, "altitude": None, "gps_fix": 0,
        }

        engine_on = is_engine_running(obd_data)

        # --- Trip start ---
        if engine_on and trip_id is None:
            trip_id = generate_trip_id()
            trip_db = create_trip_db(trip_id)
            last_engine_time = time.monotonic()
            log.info("Trip started: %s", trip_id)

        # --- Trip active: write data ---
        if engine_on and trip_db is not None:
            last_engine_time = time.monotonic()
            write_record(trip_db, trip_id, obd_data, gps_data)

            dtcs = poll_dtcs(obd_conn)
            if dtcs:
                write_dtcs(trip_db, trip_id, dtcs)

        # --- Trip end detection ---
        if trip_id is not None and not engine_on:
            idle_seconds = time.monotonic() - last_engine_time
            if idle_seconds >= config.TRIP_END_TIMEOUT_SEC:
                log.info(
                    "Trip ended: %s (idle for %ds)", trip_id, int(idle_seconds)
                )
                if trip_db is not None:
                    trip_db.close()
                trip_id = None
                trip_db = None

        # --- Maintain ~1 Hz loop ---
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0, poll_interval - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Logger stopped by user")
    except Exception:
        log.exception("Logger crashed")

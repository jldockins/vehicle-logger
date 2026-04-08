"""FastAPI ingest server — reads rsynced SQLite trip files and writes to InfluxDB.

Runs on the Unraid home server. Trip databases land in WATCH_DIR via rsync
from each vehicle's Pi. This service watches for new files, parses them,
writes data points to InfluxDB, and marks files as ingested.

Usage:
    uvicorn server.ingest:app --host 0.0.0.0 --port 8000
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
load_dotenv()

WATCH_DIR = Path(os.getenv("INGEST_WATCH_DIR", "/mnt/user/vehicle-logs"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "home")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "vehicle")
INGESTED_MANIFEST = WATCH_DIR / ".ingested.json"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Vehicle Logger Ingest", version="0.1.0")


# ---------------------------------------------------------------------------
# Manifest — tracks which trip files have been ingested into InfluxDB
# ---------------------------------------------------------------------------
def load_ingested() -> set[str]:
    if not INGESTED_MANIFEST.exists():
        return set()
    try:
        return set(json.loads(INGESTED_MANIFEST.read_text()))
    except (json.JSONDecodeError, TypeError):
        log.warning("Corrupt ingest manifest, starting fresh")
        return set()


def save_ingested(ingested: set[str]) -> None:
    INGESTED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    INGESTED_MANIFEST.write_text(json.dumps(sorted(ingested), indent=2))


# ---------------------------------------------------------------------------
# InfluxDB client
# ---------------------------------------------------------------------------
def get_influx_write_api():
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
    )
    return client, client.write_api(write_options=SYNCHRONOUS)


# ---------------------------------------------------------------------------
# Parse a trip SQLite file into InfluxDB points
# ---------------------------------------------------------------------------
OBD_FIELDS = [
    "speed_obd", "rpm", "engine_load", "coolant_temp", "throttle_pos",
    "fuel_trim_short", "fuel_trim_long", "intake_temp", "intake_pressure",
    "timing_advance", "fuel_level",
]

GPS_FIELDS = ["lat", "lon", "speed_gps", "heading", "altitude", "gps_fix"]


def parse_trip_log(db_path: Path) -> list[Point]:
    """Read the log table from a trip SQLite file and convert to InfluxDB points."""
    points = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("SELECT * FROM log ORDER BY timestamp").fetchall()
        for row in rows:
            ts = row["timestamp"]
            car_id = row["car_id"]
            trip_id = row["trip_id"]

            point = (
                Point("vehicle_data")
                .tag("car_id", car_id)
                .tag("trip_id", trip_id)
                .time(ts, WritePrecision.S)
            )

            for field in OBD_FIELDS + GPS_FIELDS:
                value = row[field]
                if value is not None:
                    point = point.field(field, float(value))

            points.append(point)
    finally:
        conn.close()

    return points


def parse_trip_dtcs(db_path: Path) -> list[Point]:
    """Read the dtcs table from a trip SQLite file and convert to InfluxDB points."""
    points = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("SELECT * FROM dtcs ORDER BY timestamp").fetchall()
        for row in rows:
            point = (
                Point("vehicle_dtc")
                .tag("car_id", row["car_id"])
                .tag("trip_id", row["trip_id"])
                .tag("code", row["code"])
                .field("description", row["description"] or "")
                .time(row["timestamp"], WritePrecision.S)
            )
            points.append(point)
    finally:
        conn.close()

    return points


# ---------------------------------------------------------------------------
# Ingest a single trip file
# ---------------------------------------------------------------------------
def ingest_file(db_path: Path, write_api) -> int:
    """Parse a trip file and write all points to InfluxDB. Returns point count."""
    log_points = parse_trip_log(db_path)
    dtc_points = parse_trip_dtcs(db_path)
    all_points = log_points + dtc_points

    if all_points:
        write_api.write(bucket=INFLUXDB_BUCKET, record=all_points)

    return len(all_points)


# ---------------------------------------------------------------------------
# Find and ingest new trip files
# ---------------------------------------------------------------------------
def find_new_trips() -> list[Path]:
    """Find trip .db files that haven't been ingested yet."""
    if not WATCH_DIR.exists():
        return []

    ingested = load_ingested()
    new_files = []

    for db_file in WATCH_DIR.rglob("*.db"):
        relative = str(db_file.relative_to(WATCH_DIR))
        if relative not in ingested:
            new_files.append(db_file)

    return sorted(new_files)


def run_ingest() -> dict[str, int]:
    """Ingest all new trip files. Returns summary stats."""
    new_trips = find_new_trips()
    if not new_trips:
        return {"files": 0, "points": 0}

    client, write_api = get_influx_write_api()
    ingested = load_ingested()
    total_points = 0
    files_ingested = 0

    try:
        for db_path in new_trips:
            relative = str(db_path.relative_to(WATCH_DIR))
            try:
                count = ingest_file(db_path, write_api)
                ingested.add(relative)
                save_ingested(ingested)
                total_points += count
                files_ingested += 1
                log.info("Ingested %s — %d points", relative, count)
            except sqlite3.Error:
                log.exception("Failed to read %s", relative)
            except Exception:
                log.exception("Failed to ingest %s", relative)
    finally:
        client.close()

    return {"files": files_ingested, "points": total_points}


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.post("/ingest")
def trigger_ingest():
    """Manually trigger ingestion of new trip files."""
    result = run_ingest()
    log.info("Ingest complete: %d files, %d points", result["files"], result["points"])
    return result


@app.get("/status")
def status():
    """Return current ingest status — how many files are pending."""
    new_trips = find_new_trips()
    ingested = load_ingested()
    return {
        "pending": len(new_trips),
        "ingested": len(ingested),
        "watch_dir": str(WATCH_DIR),
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}

"""Per-vehicle configuration for the vehicle data logger.

Safe-to-commit settings live here. Sensitive values (server IP, Bluetooth MAC,
WiFi SSID) are loaded from a .env file — see .env.example for the template.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Vehicle identity
# ---------------------------------------------------------------------------
CAR_ID: str = os.getenv("CAR_ID", "4runner")

# ---------------------------------------------------------------------------
# Hardware paths
# ---------------------------------------------------------------------------
RFCOMM_PORT: str = os.getenv("RFCOMM_PORT", "/dev/rfcomm0")
GPS_DEVICE: str = os.getenv("GPS_DEVICE", "/dev/ttyACM0")
BLUETOOTH_MAC: str = os.getenv("BLUETOOTH_MAC", "")

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
POLL_RATE_HZ: int = 1
TRIP_END_TIMEOUT_SEC: int = 60  # seconds of no OBD data before trip closes

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
TRIPS_DIR: Path = PROJECT_ROOT / "trips"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------------
# Network / sync
# ---------------------------------------------------------------------------
HOME_SSID: str = os.getenv("HOME_SSID", "")
SERVER_HOST: str = os.getenv("SERVER_HOST", "")
SERVER_USER: str = os.getenv("SERVER_USER", "nero")
SERVER_SYNC_PATH: str = os.getenv("SERVER_SYNC_PATH", "/mnt/user/vehicle-logs/")

# ---------------------------------------------------------------------------
# OBD-II PIDs to poll (python-obd command names)
# ---------------------------------------------------------------------------
OBD_PIDS: list[str] = [
    "SPEED",
    "RPM",
    "ENGINE_LOAD",
    "COOLANT_TEMP",
    "THROTTLE_POS",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "INTAKE_TEMP",
    "INTAKE_PRESSURE",
    "TIMING_ADVANCE",
    "FUEL_LEVEL",
    "CONTROL_MODULE_VOLTAGE",
]

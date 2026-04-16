"""Diagnostic: attempt to read vehicle odometer via OBD-II PID 0x01A6.

Runs standalone on the Pi while the engine is on. Does NOT modify the
production logger. Reports whether the vehicle responds to the standard
SAE J1979 odometer PID and decodes the value if the response is
well-formed.

Usage (on Pi, with engine running):
    cd ~/vehicle-logger && python scripts/test_odometer.py

The production logger service must be stopped first so it does not hold
the OBD adapter:
    sudo systemctl stop logger.service
    python scripts/test_odometer.py
    sudo systemctl start logger.service
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import obd
from obd import OBDCommand
from obd.protocols import ECU

import config

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

KM_TO_MILES = 0.621371


def decode_odometer(messages: list) -> float | None:
    """Decode mode 01 PID A6 response.

    Per SAE J1979, the four data bytes form a single 32-bit unsigned
    integer whose value is the odometer in 0.1 km increments:
        (A << 24 | B << 16 | C << 8 | D) * 0.1 km
    """
    if not messages:
        return None
    data = messages[0].data
    if not data or len(data) < 6:
        return None
    payload = data[2:6]
    raw = int.from_bytes(payload, "big")
    return raw / 10.0


def main() -> int:
    log.info("Connecting to OBD adapter at %s ...", config.RFCOMM_PORT)
    connection = obd.OBD(config.RFCOMM_PORT)

    if not connection.is_connected():
        log.error("Could not connect to OBD adapter. Is the engine on and rfcomm bound?")
        return 1

    log.info("Connected. Protocol: %s", connection.protocol_name())

    odo_cmd = OBDCommand(
        "ODOMETER",
        "Vehicle Odometer (SAE J1979 PID 0xA6)",
        b"01A6",
        6,
        decode_odometer,
        ECU.ENGINE,
        False,
    )

    log.info("Querying PID 0x01A6 (Odometer) ...")
    response = connection.query(odo_cmd, force=True)

    if response.messages:
        for i, msg in enumerate(response.messages):
            raw_hex = msg.data.hex() if msg.data else "(none)"
            log.info("  message %d raw data: %s", i, raw_hex)

    if response.is_null() or response.value is None:
        log.warning(
            "No decodable response. Vehicle likely does not support PID 0x01A6 "
            "(expected for pre-2020 vehicles)."
        )
        connection.close()
        return 2

    km = response.value
    miles = km * KM_TO_MILES
    log.info("SUCCESS: odometer = %.1f km (%.1f miles)", km, miles)

    connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

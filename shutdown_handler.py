"""Safe shutdown handler — prevents SD card corruption on power loss.

Monitors for signs that vehicle power is being cut (OBD adapter disconnected,
USB voltage drop) and triggers a clean shutdown before the Pi loses power.

Strategy:
  - When the car ignition turns off, the 12V USB adapter loses power.
  - Most adapters have enough capacitance for 2-5 seconds of hold-up.
  - This handler detects the power loss signal and immediately:
    1. Flushes any open SQLite writes
    2. Syncs the filesystem
    3. Initiates a clean shutdown

Detection methods (in priority order):
  1. USB power supply voltage drop (via /sys/class/power_supply/)
  2. OBD adapter Bluetooth disconnection (proxy for ignition off)

If GPIO headers are added later, voltage monitoring via a GPIO pin
can be added as a more reliable detection method.

Usage:
    This runs alongside logger.py, either as a separate systemd service
    or called from the logger's main loop on trip end.
"""

import logging
import subprocess
import time
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "shutdown.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# How long to wait after detecting power loss before shutting down.
# Gives time for logger.py to close its trip DB cleanly.
SHUTDOWN_DELAY_SEC: int = 5

# How often to check for power loss signals.
CHECK_INTERVAL_SEC: float = 1.0

# Path to the rfcomm device — if it disappears, Bluetooth adapter is gone.
RFCOMM_PATH = Path(config.RFCOMM_PORT)


# ---------------------------------------------------------------------------
# Detection methods
# ---------------------------------------------------------------------------
def check_usb_power() -> bool:
    """Check if USB power supply voltage is present.

    Returns True if power looks healthy, False if voltage drop detected.
    Not all Pi models expose this — returns True (healthy) if unavailable.
    """
    power_supply = Path("/sys/class/power_supply")
    if not power_supply.exists():
        return True

    for supply in power_supply.iterdir():
        status_file = supply / "status"
        if status_file.exists():
            try:
                status = status_file.read_text().strip()
                if status in ("Not charging", "Discharging"):
                    log.warning("USB power supply status: %s", status)
                    return False
            except OSError:
                continue

    return True


def check_obd_connected() -> bool:
    """Check if the OBD Bluetooth rfcomm device is still present."""
    return RFCOMM_PATH.exists()


def is_power_stable() -> bool:
    """Combine all power detection methods. Returns False if power loss detected."""
    if not check_usb_power():
        return False
    if not check_obd_connected():
        return False
    return True


# ---------------------------------------------------------------------------
# Shutdown sequence
# ---------------------------------------------------------------------------
def flush_filesystem() -> None:
    """Force sync all buffered filesystem writes to disk."""
    try:
        subprocess.run(["sync"], timeout=10, check=True)
        log.info("Filesystem synced")
    except subprocess.TimeoutExpired:
        log.error("Filesystem sync timed out")
    except Exception:
        log.exception("Filesystem sync failed")


def shutdown() -> None:
    """Initiate a clean system shutdown."""
    log.info("Initiating shutdown in %ds...", SHUTDOWN_DELAY_SEC)
    time.sleep(SHUTDOWN_DELAY_SEC)
    flush_filesystem()
    log.info("Shutting down now")
    try:
        subprocess.run(
            ["sudo", "shutdown", "-h", "now"],
            timeout=10,
            check=True,
        )
    except Exception:
        log.exception("Shutdown command failed")


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("Shutdown handler started — monitoring power state")

    # Wait for initial OBD connection before monitoring
    while not RFCOMM_PATH.exists():
        log.debug("Waiting for OBD connection at %s", RFCOMM_PATH)
        time.sleep(CHECK_INTERVAL_SEC)

    log.info("OBD connected — now monitoring for power loss")

    while True:
        if not is_power_stable():
            log.warning("Power loss detected — preparing for shutdown")
            shutdown()
            break

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutdown handler stopped by user")
    except Exception:
        log.exception("Shutdown handler crashed")

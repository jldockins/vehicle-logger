"""Sync completed trip databases to the home server over SSH.

Triggered by NetworkManager when the Pi connects to the home WiFi SSID.
Compares local trip files against a synced manifest, rsyncs new ones,
and marks them as synced to avoid re-sending.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / "sync.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sync manifest — tracks which trip files have been synced
# ---------------------------------------------------------------------------
MANIFEST_PATH: Path = config.TRIPS_DIR / ".synced.json"


def load_manifest() -> set[str]:
    """Load the set of already-synced trip file paths (relative to TRIPS_DIR)."""
    if not MANIFEST_PATH.exists():
        return set()
    try:
        data = json.loads(MANIFEST_PATH.read_text())
        return set(data)
    except (json.JSONDecodeError, TypeError):
        log.warning("Corrupt sync manifest, starting fresh")
        return set()


def save_manifest(synced: set[str]) -> None:
    """Persist the set of synced trip file paths."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(sorted(synced), indent=2))


# ---------------------------------------------------------------------------
# WiFi check
# ---------------------------------------------------------------------------
def is_on_home_wifi() -> bool:
    """Check if the Pi is currently connected to the home WiFi SSID."""
    if not config.HOME_SSID:
        log.warning("HOME_SSID not configured, skipping WiFi check")
        return False
    try:
        result = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        current_ssid = result.stdout.strip()
        return current_ssid == config.HOME_SSID
    except FileNotFoundError:
        log.warning("iwgetid not found — not running on a wireless Pi?")
        return False
    except subprocess.TimeoutExpired:
        log.warning("WiFi SSID check timed out")
        return False


# ---------------------------------------------------------------------------
# Find unsynced trips
# ---------------------------------------------------------------------------
def find_unsynced_trips() -> list[Path]:
    """Return a list of trip .db files that haven't been synced yet."""
    if not config.TRIPS_DIR.exists():
        return []

    synced = load_manifest()
    unsynced = []

    for db_file in config.TRIPS_DIR.rglob("*.db"):
        relative = str(db_file.relative_to(config.TRIPS_DIR))
        if relative not in synced:
            unsynced.append(db_file)

    return sorted(unsynced)


# ---------------------------------------------------------------------------
# Rsync a single trip file
# ---------------------------------------------------------------------------
def rsync_file(local_path: Path) -> bool:
    """Rsync a single trip database to the home server. Returns True on success."""
    relative = local_path.relative_to(config.TRIPS_DIR)
    remote_dest = (
        f"{config.SERVER_USER}@{config.SERVER_HOST}:"
        f"{config.SERVER_SYNC_PATH}/{relative}"
    )

    # Ensure remote directory exists
    remote_dir = (
        f"{config.SERVER_USER}@{config.SERVER_HOST}:"
        f"{config.SERVER_SYNC_PATH}/{relative.parent}"
    )

    try:
        # Create remote directory
        subprocess.run(
            [
                "ssh",
                f"{config.SERVER_USER}@{config.SERVER_HOST}",
                "mkdir",
                "-p",
                f"{config.SERVER_SYNC_PATH}/{relative.parent}",
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )

        # Rsync the file
        result = subprocess.run(
            [
                "rsync",
                "-az",
                "--partial",
                str(local_path),
                remote_dest,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            log.info("Synced: %s", relative)
            return True

        log.error("rsync failed for %s: %s", relative, result.stderr.strip())
        return False

    except subprocess.TimeoutExpired:
        log.error("rsync timed out for %s", relative)
        return False
    except subprocess.CalledProcessError as e:
        log.error("SSH mkdir failed for %s: %s", relative, e.stderr)
        return False
    except FileNotFoundError:
        log.error("rsync or ssh not found on this system")
        return False


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------
def sync() -> int:
    """Run a full sync cycle. Returns the number of files successfully synced."""
    if not config.SERVER_HOST:
        log.error("SERVER_HOST not configured — cannot sync")
        return 0

    unsynced = find_unsynced_trips()
    if not unsynced:
        log.info("No new trips to sync")
        return 0

    log.info("Found %d unsynced trip(s)", len(unsynced))

    synced_manifest = load_manifest()
    success_count = 0

    for trip_file in unsynced:
        if rsync_file(trip_file):
            relative = str(trip_file.relative_to(config.TRIPS_DIR))
            synced_manifest.add(relative)
            save_manifest(synced_manifest)
            success_count += 1

    log.info("Sync complete: %d/%d succeeded", success_count, len(unsynced))
    return success_count


def main() -> None:
    log.info("Sync triggered — car_id=%s", config.CAR_ID)

    if not is_on_home_wifi():
        log.info("Not on home WiFi, aborting sync")
        sys.exit(0)

    sync()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Sync stopped by user")
    except Exception:
        log.exception("Sync crashed")

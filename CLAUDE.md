# Vehicle Logger

An OBD-II + GPS vehicle data logger that runs on a Raspberry Pi Zero 2W, collects engine and location data while driving, syncs to a home server over WiFi, and displays vehicle health on a household Grafana dashboard.

The primary goal is a **glanceable household dashboard** — check vehicle health before taking a car out.

## Project Brief

The full hardware specs, architecture, data schema, and phase plan are in `vehicle-logger.md`. Read it before making architecture decisions.

## Repository Layout

```
vehicle-logger/
├── CLAUDE.md                # This file — project rules for Claude
├── vehicle-logger.md        # Full project brief and hardware specs
├── config.py                # Per-vehicle settings (car ID, BT MAC, server IP)
├── logger.py                # Main OBD + GPS polling loop (runs on Pi)
├── sync.py                  # Syncs trip data to home server over WiFi
├── shutdown_handler.py      # Safe shutdown on power loss
├── db/
│   └── schema.sql           # SQLite schema for trip databases
├── trips/                   # Local trip databases (gitignored)
├── logs/                    # Script logs (gitignored)
├── server/
│   ├── ingest.py            # FastAPI endpoint on Unraid — receives trip data
│   └── requirements.txt     # Server-side dependencies
├── systemd/
│   └── logger.service       # systemd unit file for auto-start on boot
├── setup/
│   └── setup.sh             # One-time Pi setup script
└── tests/
    └── ...                  # pytest tests with mocked hardware
```

## Key Commands

| Task | Command |
|---|---|
| Install dependencies | `pip install -r requirements.txt` |
| Run tests | `pytest tests/` |
| Run a specific test | `pytest tests/test_logger.py -v` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Lint + fix | `ruff check . --fix` |

## Tech Stack

- **Language:** Python 3.11+ (Raspberry Pi OS Bookworm)
- **OBD-II:** `python-obd` over Bluetooth rfcomm
- **GPS:** `gpsd` + `python-gps`
- **On-device storage:** SQLite (one DB per trip)
- **Sync:** rsync over SSH to home server
- **Server:** FastAPI on Unraid
- **Time series DB:** InfluxDB
- **Dashboard:** Grafana

## Git Workflow

| Rule | Details |
|---|---|
| Default branch | `main` |
| Branching | GitHub Flow — feature branches off `main`, merge via PR |
| Branch naming | `feat/description`, `fix/description`, `chore/description` |
| Commits | Conventional Commits (see below) |
| Merging | Squash merge to keep `main` history clean |

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/). The format is:

```
type(scope): short description
```

**Types:**
| Type | When to use | Example |
|---|---|---|
| `feat` | New functionality | `feat(logger): add coolant temp polling` |
| `fix` | Bug fix | `fix(sync): retry on WiFi timeout` |
| `refactor` | Code restructuring, no behavior change | `refactor(logger): extract trip detection logic` |
| `test` | Adding or updating tests | `test(sync): add mock WiFi connection tests` |
| `chore` | Config, dependencies, tooling | `chore: add ruff linter config` |
| `docs` | Documentation only | `docs: update wiring diagram` |

**Scopes** (optional): `logger`, `sync`, `server`, `shutdown`, `db`, `config`

## Code Standards

- **Python style:** Follow PEP 8, enforced by `ruff`
- **Type hints:** Use on all function signatures
- **Imports:** Group as stdlib, third-party, local — `ruff` handles ordering
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants
- **Error handling:** Log errors with `logging` module, never use bare `except:`
- **Hardware interfaces:** Always wrap in try/except with clear error messages — Bluetooth and GPS connections are unreliable

## Testing

- **Framework:** `pytest`
- **Strategy:** Mock all hardware (OBD, GPS, WiFi) — tests must run on any machine, not just the Pi
- **Test location:** `tests/` directory, mirroring source structure
- **Naming:** `test_<module>.py` with functions named `test_<behavior>`

## Secrets Policy

- **Never commit:** `.env` files, WiFi passwords, SSH keys, server credentials
- **Config values** like `CAR_ID` and `POLL_RATE_HZ` go in `config.py` (safe to commit)
- **Sensitive values** like `SERVER_HOST`, `BLUETOOTH_MAC` go in `.env` (gitignored)

## Architecture Rules

- **Never** write directly to InfluxDB from the Pi — always go through the server ingest endpoint
- **Never** assume hardware is connected — always handle missing OBD adapter or GPS gracefully
- **Never** block the main logging loop waiting for sync — sync is a separate process
- **Always** flush SQLite writes before shutdown to prevent corruption
- **Always** tag data with `car_id` and `trip_id` for multi-vehicle support
- **Always** log with timestamps in UTC

## Agent Routing

| Agent | Use for |
|---|---|
| `pi-engineer` | Anything running on the Pi — logger, sync, shutdown, systemd, Bluetooth, GPS |
| `server-engineer` | The Unraid side — FastAPI ingest, InfluxDB writes, Grafana config |
| `test-engineer` | Writing and reviewing pytest tests |

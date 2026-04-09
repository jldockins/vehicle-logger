# Session Log — 2026-04-07

## Accomplished
- Built the entire application codebase from the project brief
- Created `config.py` with `.env` support for secrets via `python-dotenv`
- Created `db/schema.sql` with `log` and `dtcs` tables, WAL mode
- Created `logger.py` — main OBD-II + GPS polling loop with trip detection
- Created `sync.py` — WiFi-triggered rsync of trip SQLite files to home server
- Created `server/ingest.py` — FastAPI endpoint that parses rsynced SQLite into InfluxDB
- Created `shutdown_handler.py` — safe shutdown via OBD disconnect detection (no GPIO needed)
- Created `systemd/logger.service` and `systemd/shutdown-handler.service`
- Created `setup/setup.sh` — one-time Pi setup script
- Created `.env.example` and `server/.env.example` templates
- Created `requirements.txt` (Pi) and `server/requirements.txt` (Unraid)
- Wrote 58 passing tests across 3 test files (test_logger, test_sync, test_ingest)
- Updated `vehicle-logger.md` to reflect VK-162 GPS receiver (replacing BU-353-S4)
- Committed and pushed to GitHub

## Current State
- **Branch**: `main`
- **Uncommitted changes**: No (only the session log is untracked)
- **Build/test status**: 58/58 tests passing

## In Progress
- Nothing actively in progress — all planned code is complete

## Decisions Made
- **GPS receiver changed**: User is buying the VK-162 (Geekstory, u-blox M8030) instead of the GlobalSat BU-353-S4 (discontinued/overpriced). Same USB/gpsd interface, no code changes needed.
- **Shutdown detection via OBD disconnect**: Since the Pi has no GPIO headers, shutdown_handler.py monitors rfcomm device presence and USB power supply status instead of a GPIO voltage pin.
- **Sync uses rsync over SSH**: Trip .db files land on the server filesystem, then ingest.py reads them — no HTTP POST from Pi needed.
- **Manifest pattern for idempotency**: Both sync.py and ingest.py use JSON manifest files (.synced.json, .ingested.json) to track processed files, saving after each file for crash safety.
- **conftest.py mocks hardware modules**: `obd` and `gps` Python packages aren't available on Python 3.14 (Mac), so conftest.py stubs them at the sys.modules level so tests run anywhere.
- **Secrets in .env, config in config.py**: SERVER_HOST, BLUETOOTH_MAC, HOME_SSID, INFLUXDB_TOKEN go in .env (gitignored). CAR_ID, POLL_RATE_HZ, OBD_PIDS stay in config.py (safe to commit).

## Hardware Status
- **Ordered**: Pi Zero 2W Basic Kit + USB OTG cable (CanaKit)
- **Arriving tomorrow (2026-04-08)**: Vgate iCar Pro Bluetooth 3.0 OBD-II adapter
- **Still need to order**: VK-162 USB GPS receiver (Geekstory, u-blox M8030, ~$12-15 on Amazon)

## Open Questions / Blockers
- Hardware hasn't arrived yet — no on-device testing possible
- `ANTHROPIC_API_KEY` secret still needs to be added to GitHub repo for CI review workflow
- Safe shutdown timing is a guess (5s delay) — needs real-world testing with the actual USB car adapter's capacitor hold-up time
- rfcomm persistence across reboots not yet handled (needs rc.local or a systemd oneshot)

## Next Steps
1. Order the VK-162 GPS receiver
2. When Pi arrives: flash Raspberry Pi OS Lite, clone repo, run `setup/setup.sh`
3. Pair OBD adapter via bluetoothctl, test with `cgps -s` for GPS
4. Test logger.py with real hardware — verify OBD PIDs and GPS data
5. Set up InfluxDB + Grafana on Unraid
6. Deploy server/ingest.py on Unraid
7. Test full end-to-end: drive → log → come home → sync → ingest → Grafana
8. Build initial Grafana dashboard (vehicle health focus)

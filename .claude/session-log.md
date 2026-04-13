# Session Log — 2026-04-12

## Accomplished
- Finished Grafana dashboard `Vehicle Health` with 8 panels: Speed (time series, mph), RPM (time series), Coolant Temp (stat, °F), Fuel Level (gauge, %), Engine Load (time series, %), GPS Track (geomap route, default view Concord NH↔Boston), Max Speed (stat, mph), Battery Voltage (stat, V — no data yet, needs next drive).
- Added battery voltage PID to the logger pipeline: `CONTROL_MODULE_VOLTAGE` added to `config.py`, `logger.py` (PID_TO_COLUMN), `db/schema.sql`, and `server/ingest.py` (OBD_FIELDS). Tests pass (63/63). Only takes effect for new trip databases.
- Discussed odometer PID — python-obd doesn't have a standard command for it. PID 0x01A6 was standardized in 2019+ specs but likely unsupported on the van. Deferred.
- Identified that `sync.py` has no systemd unit or automatic trigger — the code is written but nothing runs it. Chose Option B (NetworkManager dispatcher) for tomorrow.

## Current State
- **Branch**: `main`
- **Uncommitted changes**: `config.py`, `logger.py`, `db/schema.sql`, `server/ingest.py` (battery voltage additions), `.claude/session-log.md`
- **Build/test status**: 63/63 passing on Mac
- **Unpushed commits**: none new — working tree has uncommitted edits

## In Progress
- **End-to-end test drive** — blocked on sync automation (no trigger for `sync.py` yet)

## Decisions Made
- **NetworkManager dispatcher over systemd timer** for sync trigger. More responsive (fires the moment Pi connects to home WiFi) vs polling every N minutes. User chose this approach.
- **Battery voltage added as `CONTROL_MODULE_VOLTAGE`** → `battery_voltage` column in volts. Standard PID, should work on most vehicles.
- **Odometer deferred.** Not a standard python-obd command; PID 0x01A6 likely unsupported on older vans. Can attempt a custom query on a future test drive.
- **GPS Track panel uses Route layer type** — draws connected lines between points instead of individual dots. Default view centered on 42.78°N, -71.3°W, zoom 9 (Concord NH to Boston corridor).
- **Dashboard layout polish deferred** — user will fine-tune panel sizes/arrangement once all panels are final.

## Open Questions / Blockers
- **No sync trigger exists yet.** `sync.py` needs a NetworkManager dispatcher script on the Pi to fire when connecting to home WiFi. Without this, trip data won't flow automatically after a drive.
- **Updated logger.py not yet deployed to Pi.** Battery voltage PID is only in the local repo. Need to pull on Pi after committing.
- **Docker ingest image on Unraid needs rebuild** after `battery_voltage` is added to ingest.py. `cd /mnt/user/appdata/vehicle-ingest && git pull && docker build -t vehicle-ingest .`
- **Pre-fix trip DBs still on Pi** (`20260409-*.db`) — not worth ingesting, can delete when convenient.
- **RPM panel didn't persist from yesterday.** User had to recreate it. Possible cause: didn't save the dashboard before closing. Reminded user to save (💾) after changes.

## Next Steps
1. **Create NetworkManager dispatcher** for `sync.py` on the Pi — fires on home WiFi connect.
2. **Commit and push** the battery voltage changes.
3. **Deploy to Pi** — `git pull` on the Pi to get the updated logger with battery voltage.
4. **Rebuild ingest Docker image on Unraid** — `git pull` + `docker build -t vehicle-ingest .` in `/mnt/user/appdata/vehicle-ingest/`.
5. **Full end-to-end test drive.** Drive van, come home, verify sync fires automatically, ingest cron picks up the file, Grafana renders new trip with battery voltage. Closes Phase 1.
6. **Dashboard layout polish** — resize and arrange panels for optimal glanceability.

## Macropad Hub
- No hub issues. Title is "Vehicle Data Logger", CLAUDE.md present.
- ⚠️ No scripts configured in hub config (low priority).

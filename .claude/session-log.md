# Session Log — 2026-04-16

## Accomplished
- **Dashboard polish**: Added color thresholds to Fuel Level (red/yellow/green), Battery Voltage (12.0/12.4V), and Coolant Temp (160/220/230°F) panels in Grafana. User kept their existing 4-panel top row layout (Battery Voltage, Max Speed, Fuel Level, Coolant Temp). Created `docs/dashboard-layout.md` as a reference for panel sizing and threshold values.
- **Odometer PID experiment**: Attempted standard SAE J1979 PID 0x01A6 on the 2014 Dodge Grand Caravan. **Result: not supported.** Expected for pre-2019 vehicles. User declined GPS-derived distance as an alternative.
- **Odometer probe integrated into logger**: `probe_odometer()` runs once per trip start — silent on unsupported vehicles, logs at INFO when a value is returned. Future-proofed for multi-vehicle support without log noise.
- **Standalone `scripts/test_odometer.py` kept** as a diagnostic template despite being superseded by the logger-integrated probe.
- **Recovered stuck trip data**: Trip `20260416-1835.db` had unflushed WAL sidecar files due to a logger bug. Manually ran `PRAGMA wal_checkpoint(TRUNCATE)`, removed from sync manifest, re-synced to Unraid.

## Current State
- **Branch**: `main`
- **Uncommitted changes**: none
- **Unpushed commits**: none
- **Build/test status**: 63/63 passing on Mac
- **Pi deployment**: up to date with `main` at `43d30d8`

## In Progress
- **Trip-end detection bug** — identified but NOT yet fixed. See "Open Questions" below.

## Decisions Made
- **User's dashboard layout stands**: 4 panels in top row (Battery Voltage, Max Speed, Fuel Level, Coolant Temp) instead of the proposed 3-panel health row. User prefers their arrangement.
- **Odometer PID 0x01A6 unsupported on 2014 Grand Caravan** — confirmed via live probe. Probe stays in logger (silent on failure) for future vehicles.
- **GPS-derived trip distance declined** — user said "I don't really need it."
- **ELM327 adapter instability after release/rebind cycles** — standalone scripts that share `/dev/rfcomm0` with the logger are fragile. The logger-integrated probe approach avoids this entirely.

## Open Questions / Blockers
- **Bug: trip-end detection skipped when OBD adapter flaps post-drive.** After the engine turns off, the adapter enters an "ignition is off" error loop. The main loop's `continue` in the OBD reconnect branch skips trip-end detection, so the 60-second idle timer never fires and the trip stays open with unflushed WAL. Fix: move trip-end detection above the OBD reconnect check, or track wall-clock time since last successful poll independently.
- **Dashboard data for 2026-04-16 drives** — the 1835 trip was re-synced to Unraid after WAL recovery, but it's unclear whether the server-side ingest re-processed it (it may have been marked as already ingested from the earlier stale sync). User hasn't confirmed dashboard status.
- **Sync doesn't detect changed files** — `sync.py` uses a filename-based manifest with no size/mtime tracking. If a file changes after sync (e.g., WAL flush), it's never re-uploaded unless manually removed from the manifest. Consider adding size or checksum tracking.

## Next Steps
1. **Fix the trip-end detection bug in `logger.py`** — this is the highest priority. The `continue` at line ~305 skips the trip-end block when OBD reconnection fails. Trip-end detection must run even when the adapter is unavailable. Proposed fix: check `trip_id is not None` and wall-clock idle time BEFORE the OBD reconnect check.
2. **Verify 2026-04-16 drive data on dashboard** — check Grafana for today's trips. If missing, investigate server-side ingest re-processing.
3. **Consider hardening `sync.py`** — add size-based change detection so re-syncs happen automatically when a trip file changes post-flush.
4. **Clean up old pre-fix trip DBs** — `20260409-*.db` files still on Pi and Unraid. Low priority housekeeping.

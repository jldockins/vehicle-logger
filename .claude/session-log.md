# Session Log — 2026-04-13

## Accomplished
- Committed and pushed battery voltage PID changes (`56c327d`).
- Created NetworkManager dispatcher on Pi (`/etc/NetworkManager/dispatcher.d/99-vehicle-sync`) — fires `sync.py` as `nero` whenever `wlan0` connects. No systemd timer needed.
- Deployed updated code to Pi (`git stash --include-untracked && git pull`), restarted `logger.service`.
- Rebuilt Docker ingest image on Unraid (`git pull && docker build -t vehicle-ingest .`).
- **Successful end-to-end test drive** — two real drives. Both trip files (`20260413-1837.db`, `20260413-1959.db`) synced automatically on WiFi connect, ingest cron picked them up, all 8 Grafana panels rendered real data. Battery voltage reads 14.3V (healthy alternator). **Phase 1 is complete.**
- Polished dashboard panels: fixed ugly metadata labels on Stat panels using `group() |> last()` pattern and Display name overrides. Turned off sparklines. Fixed Fuel Level gauge, Coolant Temp, Max Speed, Battery Voltage panels.
- Added Trouble Codes (DTCs) table panel with date-only timestamp, column ordering via Transform.
- Discussed and decided against Engine Load, RPM, and Last Drive panels — not useful for the household dashboard use case.

## Current State
- **Branch**: `main`
- **Uncommitted changes**: none (only an untracked screenshot PNG in the root — can delete)
- **Build/test status**: 63/63 passing on Mac
- **Unpushed commits**: none

## Dashboard — Final Panels
| Panel | Type | Query notes |
|---|---|---|
| Speed | Time series | km/h→mph conversion, shows all trips in range |
| Max Speed | Stat | `group() |> max()` for single value across trips |
| Coolant Temp | Stat | `group() |> last()`, °C→°F conversion |
| Fuel Level | Gauge | `group() |> last()`, 0-100% |
| Battery Voltage | Stat | `group() |> last()`, volts |
| GPS Track | Geomap (Route) | lat/lon join, default view Concord NH↔Boston zoom 9 |
| Trouble Codes | Table | `vehicle_dtc` measurement, date + code + description columns |

## Decisions Made
- **Dropped Engine Load and RPM panels** — not useful for glanceable household dashboard. Can add back later for diagnostics.
- **Dropped Last Drive panel** — user didn't find "2 hours ago" stat useful since they know when they drove.
- **NetworkManager dispatcher over systemd timer** for sync — fires instantly on WiFi connect rather than polling.
- **`group() |> last()` pattern** for Stat panels — merges all trip series into one so only a single latest value shows instead of one per trip.
- **Old pre-fix trip DBs (April 9) synced to Unraid** but not ingested (ingest likely failed on schema mismatch). Not worth fixing — diagnostic data only.

## Open Questions / Blockers
- **Pre-fix trip DBs on Unraid** (`20260409-*.db`) — synced but not ingested. Could delete from `/mnt/user/vehicle-logs/van/` when convenient.
- **Pre-fix trip DBs on Pi** (`20260409-*.db`) — still on the Pi with orphaned WAL/SHM sidecars. Can delete.
- **Dashboard layout not polished** — panels work but sizing/arrangement could be optimized for glanceability.
- **Odometer PID** — deferred. Could attempt custom PID 0x01A6 on a future drive.
- **Screenshot in repo root** — `Screenshot 2026-04-13 at 4.50.03 PM.png` is untracked, should be deleted or gitignored.

## Next Steps
1. **Polish dashboard layout** — resize and rearrange panels for optimal household glanceability.
2. **Clean up old trip DBs** — delete pre-fix `20260409-*.db` files from both Pi and Unraid.
3. **Delete screenshot** from repo root.
4. **Consider Phase 2 features** from `vehicle-logger.md` — multi-vehicle support, trip summary stats, alerting on high coolant temp or low battery voltage.
5. **Pi lives in the van now** — the system is fully automated. Every drive syncs and appears on the dashboard.

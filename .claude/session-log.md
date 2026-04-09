# Session Log — 2026-04-09

## Accomplished
- Flashed Pi Zero 2W with Raspberry Pi OS Lite (hostname: van-logger, user: nero)
- Cloned repo, installed all dependencies (obd, python-dotenv, gps, pytest, ruff)
- Fixed setup.sh: removed `rfcomm` package (doesn't exist on Bookworm), replaced with `bluez-tools`
- Fixed requirements.txt: package name is `obd` not `python-obd`
- GPS receiver (VK-162) detected as `/dev/ttyACM0` (not `/dev/ttyUSB0`) — updated gpsd config and all code
- Paired Vgate iCar Pro Bluetooth OBD adapter (MAC: 10:21:3E:4F:43:70, shows as "V-LINK")
- Bound rfcomm: `sudo rfcomm bind /dev/rfcomm0 10:21:3E:4F:43:70 1`
- Two successful test drives with real data capture
- First drive: 676 rows, GPS intermittent (288/676 rows with fix) — identified blocking gpsd issue
- Fixed poll_gps to use `session.waiting()` for non-blocking reads
- Second drive: 273 rows, 100% GPS coverage — fix confirmed working
- 59/59 tests passing locally

## Current State
- **Branch**: `main`
- **Uncommitted changes**: No (session log not yet written at time of commit)
- **Build/test status**: 59/59 tests passing on Mac, 44/44 Pi-side tests passing on Pi

## In Progress
- GPS speed discrepancy: GPS speed reads ~60% of OBD speed at steady state (e.g., OBD 30 mph → GPS 18 mph)
- Need to check raw gpsd TPV output while driving (`gpspipe -w | grep speed`) to determine if it's a unit issue
- gpsd WATCH config shows `scaled: false`, so speed should be in m/s — but the ratio doesn't match any obvious unit confusion

## Decisions Made
- **First vehicle is the van**, not the 4Runner as originally planned
- **Hostname**: `van-logger` (pattern: `{vehicle}-logger` for fleet)
- **Username**: `nero` (not the default `pi`)
- **OBD adapter name**: Shows as "V-LINK" in Bluetooth, not "Vgate" or "iCar"
- **GPS device path**: `/dev/ttyACM0` (VK-162 u-blox uses ACM, not ttyUSB)
- **Repo made public** temporarily for git pull to Pi, then back to private
- **rfcomm persistence not yet solved** — needs to be re-bound after reboot

## Open Questions / Blockers
- **GPS speed mismatch** — need to diagnose with `gpspipe` while driving. Could be: OBD speedometer inflation (~10%), unit conversion bug, or stale GPS data
- **rfcomm not persistent across reboots** — need to add to rc.local or a systemd oneshot service
- **PATH on Pi** — `~/.local/bin` not on PATH by default, pytest/ruff not available without `export PATH="$HOME/.local/bin:$PATH"`
- Server side (InfluxDB + Grafana on Unraid) not yet set up

## Hardware Confirmed Working
- Pi Zero 2W: running, SSH accessible at `van-logger.local`
- VK-162 GPS: 3D fix, 15+ satellites, `/dev/ttyACM0`
- Vgate iCar Pro BT 3.0: paired, trusted, rfcomm bound at `/dev/rfcomm0`, MAC `10:21:3E:4F:43:70`

## Next Steps
1. Diagnose GPS speed issue — run `gpspipe -w` while driving to check raw speed values
2. Fix rfcomm persistence across reboots (systemd oneshot or rc.local)
3. Add `~/.local/bin` to PATH in `.bashrc` on Pi
4. Set up InfluxDB + Grafana on Unraid
5. Deploy server/ingest.py on Unraid
6. Test full sync: drive → come home on WiFi → sync → ingest → dashboard

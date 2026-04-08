# Vehicle Data Logger — Project Brief

## Project Overview

A per-vehicle data logging system that collects OBD-II engine data and GPS location while driving, then automatically syncs trip data to a home server when the vehicle returns home and connects to the home WiFi network. Data is stored and visualized via InfluxDB + Grafana on an Unraid home server.

The system will eventually be deployed across 3 vehicles. Development begins with a single prototype unit installed in a 2008 Toyota 4Runner.

---

## Hardware (Per Vehicle)

| Component | Model | Purpose |
|---|---|---|
| Single-board computer | Raspberry Pi Zero 2W | Main compute, runs all scripts |
| OBD-II adapter | Vgate iCar Pro Bluetooth 3.0 | Engine data via Classic Bluetooth |
| GPS receiver | VK-162 (u-blox M8030, Geekstory) | Location data via USB |
| USB OTG adapter | Micro USB to USB-A | Connects GPS to Pi Zero |
| Storage | 32GB microSD | OS + trip data |
| Power | 12V USB car adapter | Powers Pi from cigarette lighter |

---

## System Architecture

```
[OBD-II Port] --> [Vgate iCar Pro BT 3.0] --> (Bluetooth rfcomm) --> [Pi Zero 2W]
[GPS Antenna] --> [GlobalSat BU-353-S4] --> (USB/gpsd) --> [Pi Zero 2W]
                                                                    |
                                                              [SQLite DB]
                                                            (trip logs on SD)
                                                                    |
                                          (arrives home, connects to WiFi)
                                                                    |
                                                         [rsync / HTTP POST]
                                                                    |
                                                        [Unraid Home Server]
                                                                    |
                                                      [InfluxDB + Grafana]
```

---

## Software Stack

- **OS:** Raspberry Pi OS Lite (32-bit, Bookworm)
- **OBD library:** `python-obd`
- **GPS daemon:** `gpsd` + `gpsd-clients` + `python-gps`
- **Database:** SQLite (on-device, per trip)
- **Sync:** `rsync` over SSH or HTTP POST to home server endpoint
- **Home server ingestion:** Flask or FastAPI endpoint (running on Unraid)
- **Time series storage:** InfluxDB
- **Visualization:** Grafana

---

## Data Collected

### OBD-II (via python-obd)
- Vehicle speed (mph)
- RPM
- Engine load (%)
- Coolant temperature
- Throttle position
- Short and long term fuel trim
- Intake air temperature
- Manifold absolute pressure
- Ignition timing advance
- Fuel tank level
- Active and pending DTCs (fault codes)

### GPS (via gpsd)
- Latitude / Longitude
- GPS speed (cross-reference with OBD speed)
- Heading
- Altitude
- Fix quality / satellite count

### Derived / Computed
- Trip distance
- Trip duration
- Idle time vs moving time
- Hard acceleration / braking events (delta speed over time)
- Estimated fuel consumption

---

## Data Schema

Each log entry (written at ~1Hz polling rate):

```python
{
  "timestamp": "2026-04-06T14:23:01Z",
  "car_id": "4runner",          # unique per vehicle
  "trip_id": "20260406-1420",   # YYYYMMDD-HHMM of trip start
  "speed_obd": 45.2,            # mph from OBD
  "speed_gps": 44.8,            # mph from GPS
  "rpm": 1850,
  "engine_load": 32.5,
  "coolant_temp": 195,
  "throttle_pos": 18.2,
  "fuel_trim_short": 1.5,
  "fuel_trim_long": -0.8,
  "intake_temp": 72,
  "map": 101.3,
  "timing_advance": 12.0,
  "fuel_level": 68.0,
  "lat": 42.9956,
  "lon": -71.4548,
  "heading": 182.3,
  "altitude": 213.0,
  "gps_fix": 3,                 # 0=no fix, 2=2D, 3=3D
  "dtcs": []                    # list of active fault codes
}
```

Trips are stored as SQLite databases: `trips/4runner/20260406-1420.db`

---

## Key Scripts to Build

### 1. `logger.py` — Main logging loop
- Connects to Vgate via `rfcomm` (Classic Bluetooth serial)
- Connects to `gpsd` for GPS data
- Polls OBD PIDs at ~1Hz
- Merges OBD + GPS into single timestamped record
- Writes to SQLite, one DB per trip
- Detects trip start (ignition on / speed > 0) and trip end (no OBD data / speed = 0 for N seconds)
- Runs as a `systemd` service, starts on boot

### 2. `sync.py` — Home network sync
- Triggered by `NetworkManager` dispatcher when home WiFi SSID connects
- Compares local trip files against what's already been synced
- `rsync`s new/incomplete trip files to home server over SSH
- Marks synced trips to avoid re-sending
- Logs sync activity

### 3. `shutdown_handler.py` — Safe shutdown
- Monitors for power loss (GPIO pin or voltage drop detection)
- Flushes open SQLite writes
- Calls `sudo shutdown -h now`
- Prevents SD card corruption on hard power cut

### 4. `server/ingest.py` — Home server receiver (Unraid)
- Flask or FastAPI endpoint
- Accepts rsync'd SQLite files or JSON POST batches
- Parses and writes to InfluxDB
- Tags all data with `car_id` and `trip_id`

---

## Bluetooth Setup (One-Time on Pi)

```bash
# Pair Vgate iCar Pro BT 3.0
bluetoothctl
  power on
  scan on
  pair <MAC_ADDRESS>
  trust <MAC_ADDRESS>
  quit

# Bind rfcomm serial port
sudo rfcomm bind /dev/rfcomm0 <MAC_ADDRESS> 1

# Make persistent (add to /etc/rc.local or systemd service)
```

---

## GPS Setup (One-Time on Pi)

```bash
# Install gpsd
sudo apt install gpsd gpsd-clients python3-gps

# Configure gpsd to use USB GPS
sudo nano /etc/default/gpsd
# Set: DEVICES="/dev/ttyUSB0"
# Set: GPSD_OPTIONS="-n"

sudo systemctl enable gpsd
sudo systemctl start gpsd

# Test
cgps -s
```

---

## Home Network Sync Trigger (NetworkManager Dispatcher)

```bash
# /etc/NetworkManager/dispatcher.d/99-home-sync
#!/bin/bash
SSID="$2"
EVENT="$1"
HOME_SSID="YourHomeNetworkName"

if [[ "$EVENT" == "up" && "$SSID" == "$HOME_SSID" ]]; then
    /usr/bin/python3 /home/pi/vehicle-logger/sync.py &
fi
```

---

## Grafana Dashboard Ideas

- **Trip Map** — GPS route overlaid on map panel
- **Speed over Time** — OBD vs GPS speed comparison
- **RPM + Engine Load** — dual axis timeline
- **Coolant Temp** — trip warmup curve
- **Fuel Trim** — short/long term, useful for diagnosing running issues
- **Fault Code History** — table of DTCs per car per trip
- **Fleet Overview** — all 3 cars, last seen, last trip distance, any active DTCs

---

## systemd Services

### logger.service
```ini
[Unit]
Description=Vehicle OBD + GPS Logger
After=bluetooth.target gpsd.service
Wants=bluetooth.target gpsd.service

[Service]
ExecStart=/usr/bin/python3 /home/pi/vehicle-logger/logger.py
Restart=on-failure
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

---

## Project Structure

```
vehicle-logger/
├── logger.py               # Main OBD + GPS logging loop
├── sync.py                 # Home WiFi sync script
├── shutdown_handler.py     # Safe shutdown on power loss
├── config.py               # Car ID, home SSID, server address, PIDs to poll
├── db/
│   └── schema.sql          # SQLite schema
├── trips/                  # Local trip databases (synced and cleared periodically)
├── logs/                   # Script logs
├── server/
│   ├── ingest.py           # Flask/FastAPI ingest endpoint (runs on Unraid)
│   └── requirements.txt
├── systemd/
│   └── logger.service      # systemd unit file
├── setup/
│   └── setup.sh            # One-time Pi setup script
└── README.md
```

---

## Config File (`config.py`)

```python
CAR_ID = "4runner"
HOME_SSID = "YourHomeNetworkName"
SERVER_HOST = "192.168.1.x"       # Unraid server IP
SERVER_USER = "pi"
SERVER_SYNC_PATH = "/mnt/user/vehicle-logs/"
BLUETOOTH_MAC = "AA:BB:CC:DD:EE:FF"   # Vgate iCar Pro MAC
RFCOMM_PORT = "/dev/rfcomm0"
GPS_DEVICE = "/dev/ttyUSB0"
POLL_RATE_HZ = 1
TRIP_END_TIMEOUT_SEC = 60         # seconds of inactivity before trip is closed
```

---

## Phase 1 — Prototype (4Runner)

- [ ] Flash Pi Zero 2W with Raspberry Pi OS Lite
- [ ] Pair Vgate iCar Pro BT 3.0 via bluetoothctl
- [ ] Configure gpsd with GlobalSat BU-353-S4
- [ ] Build and test `logger.py`
- [ ] Verify SQLite trip files are being written correctly
- [ ] Set up home server ingest endpoint on Unraid
- [ ] Build and test `sync.py` triggered by NetworkManager
- [ ] Set up InfluxDB + Grafana on Unraid
- [ ] Build initial Grafana dashboard
- [ ] Install `logger.service` as systemd service
- [ ] Test full end-to-end: drive → come home → data appears in Grafana

## Phase 2 — Fleet Rollout (Cars 2 + 3)

- [ ] Clone SD card image from working 4Runner unit
- [ ] Update `config.py` per vehicle (CAR_ID, Bluetooth MAC)
- [ ] Order and install hardware for remaining vehicles
- [ ] Add per-car dashboards in Grafana

---

## Notes

- Pi Zero 2W has one micro USB port — USB OTG adapter required for GPS dongle
- Power the Pi from an ignition-switched 12V source long-term to avoid battery drain
- Add a graceful shutdown circuit (or supervise power pin) to prevent SD card corruption on hard power cut
- The Vgate iCar Pro BT 3.0 is Android-only for phone apps — this is fine, the Pi uses Classic Bluetooth rfcomm which works perfectly
- 2008 Toyota 4Runner is full OBD-II compliant — all standard PIDs available
- Future enhancement: add IMU (MPU-6050 via I2C) for g-force / cornering data

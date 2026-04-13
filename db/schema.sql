-- Trip database schema — one SQLite file per trip.
-- Created automatically by logger.py at trip start.

CREATE TABLE IF NOT EXISTS log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,  -- ISO-8601 UTC
    car_id      TEXT    NOT NULL,
    trip_id     TEXT    NOT NULL,  -- YYYYMMDD-HHMM of trip start

    -- OBD-II (canonical SI units — dashboard converts for display)
    speed_obd       REAL,   -- km/h
    rpm             REAL,
    engine_load     REAL,   -- percent
    coolant_temp    REAL,   -- °C
    throttle_pos    REAL,   -- percent
    fuel_trim_short REAL,
    fuel_trim_long  REAL,
    intake_temp     REAL,   -- °C
    intake_pressure REAL,   -- kPa (MAP)
    timing_advance  REAL,   -- degrees
    fuel_level      REAL,   -- percent
    battery_voltage REAL,   -- volts

    -- GPS
    lat         REAL,
    lon         REAL,
    speed_gps   REAL,   -- km/h
    heading     REAL,   -- degrees
    altitude    REAL,   -- meters
    gps_fix     INTEGER -- 0=no fix, 2=2D, 3=3D
);

CREATE TABLE IF NOT EXISTS dtcs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,  -- ISO-8601 UTC
    car_id      TEXT    NOT NULL,
    trip_id     TEXT    NOT NULL,
    code        TEXT    NOT NULL,  -- e.g. P0301
    description TEXT               -- human-readable if available
);

-- Index for time-range queries during sync and dashboard display.
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log(timestamp);
CREATE INDEX IF NOT EXISTS idx_dtcs_timestamp ON dtcs(timestamp);

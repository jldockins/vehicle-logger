# Grafana Dashboard Layout

Household "check before you drive" vehicle health dashboard. Optimized for glanceability from across the room.

**URL:** http://192.168.4.67:3000

## Design Principle

Two-second glance test: can someone across the room tell at a glance whether the van is healthy and ready to drive? Health indicators go big and bold at the top; context and visuals go smaller toward the bottom.

## Layout

Grafana uses a 24-column grid. Heights are in grid units (1 unit ≈ 30px).

### Row 1 — At a glance
Four equal panels side by side.

| Panel | Type | Width | Height |
|---|---|---|---|
| Battery Voltage | Stat | 6 | 8 |
| Max Speed | Stat | 6 | 8 |
| Fuel Level | Gauge | 6 | 8 |
| Coolant Temp | Stat | 6 | 8 |

### Row 2 — Trouble codes
Full width, short. Empty = good news. Any row = visually loud.

| Panel | Type | Width | Height |
|---|---|---|---|
| Trouble Codes (DTCs) | Table | 24 | 5 |

### Row 3 — Speed
| Panel | Type | Width | Height |
|---|---|---|---|
| Speed | Time series | 24 | 7 |

### Row 4 — GPS track
Nice-to-have visual. Full width, tall.

| Panel | Type | Width | Height |
|---|---|---|---|
| GPS Track | Geomap | 24 | 10 |

## Thresholds

Set via panel edit → Thresholds pane. Use Percentage mode = Absolute.

### Battery Voltage (volts)
| Range | Color |
|---|---|
| > 12.4 | Green |
| 12.0 – 12.4 | Yellow |
| < 12.0 | Red |

### Fuel Level (%)
| Range | Color |
|---|---|
| > 50 | Green |
| 25 – 50 | Yellow |
| < 25 | Red |

### Coolant Temp (°F)
| Range | Color |
|---|---|
| 160 – 220 | Green |
| 220 – 230 | Yellow |
| > 230 | Red |

Coolant thresholds use a banded approach — too cold is also abnormal, but engines warm up on every drive so we don't flag the low end red.

## Notes

- Keep Stat panels using the `group() |> last()` pattern so one value shows across all trips, not one per trip.
- Sparklines stay OFF on health stat panels (decided 2026-04-13).
- Default dashboard time range: **Last 7 days** — short enough to feel current, long enough to always show the last drive.

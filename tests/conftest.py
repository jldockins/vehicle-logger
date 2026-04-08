"""Conftest — mock hardware modules that aren't available outside the Pi."""

import sys
from unittest.mock import MagicMock

# Mock the hardware-only modules so tests can import logger.py on any machine.
# These must be set before importing logger.
obd_mock = MagicMock()
gps_mock = MagicMock()

sys.modules["obd"] = obd_mock
sys.modules["gps"] = gps_mock

# Re-export the mock constants that logger.py imports at module level
gps_mock.WATCH_ENABLE = 0x01
gps_mock.WATCH_NEWSTYLE = 0x02

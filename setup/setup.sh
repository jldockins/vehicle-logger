#!/bin/bash
# One-time setup script for the Raspberry Pi Zero 2W.
# Run as root: sudo bash setup/setup.sh
#
# What this does:
#   1. Installs system packages (gpsd, Bluetooth, Python deps)
#   2. Configures gpsd for the USB GPS receiver
#   3. Installs Python dependencies
#   4. Creates required directories
#   5. Installs systemd services
#   6. Prints next steps for manual Bluetooth pairing

set -euo pipefail

PROJECT_DIR="/home/nero/vehicle-logger"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------------------------------------------------------------------------
# Check we're running as root
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo bash setup/setup.sh)"
    exit 1
fi

echo "=== Vehicle Logger — Pi Setup ==="
echo ""

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
echo "[1/5] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3-pip \
    python3-venv \
    gpsd \
    gpsd-clients \
    python3-gps \
    bluetooth \
    bluez \
    bluez-tools \
    rsync \
    wireless-tools

echo "      Done."

# ---------------------------------------------------------------------------
# 2. Configure gpsd
# ---------------------------------------------------------------------------
echo "[2/5] Configuring gpsd..."

cat > /etc/default/gpsd << 'EOF'
# GPS device — VK-162 USB GPS receiver
DEVICES="/dev/ttyACM0"
GPSD_OPTIONS="-n"
USBAUTO="true"
START_DAEMON="true"
EOF

systemctl enable gpsd
systemctl restart gpsd

echo "      Done."

# ---------------------------------------------------------------------------
# 3. Python dependencies
# ---------------------------------------------------------------------------
echo "[3/5] Installing Python dependencies..."
pip3 install --break-system-packages -r "${PROJECT_DIR}/requirements.txt"
echo "      Done."

# ---------------------------------------------------------------------------
# 4. Create directories
# ---------------------------------------------------------------------------
echo "[4/5] Creating directories..."
mkdir -p "${PROJECT_DIR}/trips"
mkdir -p "${PROJECT_DIR}/logs"
chown -R nero:nero "${PROJECT_DIR}/trips" "${PROJECT_DIR}/logs"
echo "      Done."

# ---------------------------------------------------------------------------
# 5. Install systemd services
# ---------------------------------------------------------------------------
echo "[5/5] Installing systemd services..."

cp "${PROJECT_DIR}/systemd/logger.service" /etc/systemd/system/
cp "${PROJECT_DIR}/systemd/shutdown-handler.service" /etc/systemd/system/
cp "${PROJECT_DIR}/systemd/rfcomm-bind.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable logger.service
systemctl enable shutdown-handler.service
systemctl enable rfcomm-bind.service

echo "      Done."

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Before starting the logger, you need to:"
echo ""
echo "  1. Pair the Vgate iCar Pro Bluetooth adapter:"
echo "     $ bluetoothctl"
echo "       power on"
echo "       scan on"
echo "       pair <MAC_ADDRESS>"
echo "       trust <MAC_ADDRESS>"
echo "       quit"
echo ""
echo "  2. Bind rfcomm (replace MAC with your adapter's address):"
echo "     $ sudo rfcomm bind /dev/rfcomm0 <MAC_ADDRESS> 1"
echo ""
echo "  3. Copy .env.example to .env and fill in your values:"
echo "     $ cp ${PROJECT_DIR}/.env.example ${PROJECT_DIR}/.env"
echo "     $ nano ${PROJECT_DIR}/.env"
echo ""
echo "  4. Test the GPS receiver:"
echo "     $ cgps -s"
echo ""
echo "  5. Start the services:"
echo "     $ sudo systemctl start logger.service"
echo "     $ sudo systemctl start shutdown-handler.service"
echo ""
echo "  6. Check logs:"
echo "     $ journalctl -u logger.service -f"
echo "     $ tail -f ${PROJECT_DIR}/logs/logger.log"

#!/usr/bin/env bash
set -euo pipefail

WIFI_IFACE="${RPI2W_WIFI_INTERFACE:-wlan0}"
HOTSPOT_CONNECTION="${RPI2W_HOTSPOT_CONNECTION_NAME:-rpi2w-hotspot}"
HOTSPOT_SSID="${RPI2W_HOTSPOT_SSID:-rpi2w-setup}"
HOTSPOT_PASSWORD="${RPI2W_HOTSPOT_PASSWORD:-rpi2w-setup-pass}"

if ! command -v nmcli >/dev/null 2>&1; then
    echo "nmcli is required for fallback hotspot management" >&2
    exit 1
fi

device_line="$(nmcli -t -f DEVICE,STATE,CONNECTION dev status | awk -F: -v iface="$WIFI_IFACE" '$1 == iface {print; exit}')"
device_state="$(printf '%s' "$device_line" | cut -d: -f2)"
active_connection="$(printf '%s' "$device_line" | cut -d: -f3-)"

if [[ "$device_state" == "connected" && "$active_connection" != "$HOTSPOT_CONNECTION" ]]; then
    nmcli connection down "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
    exit 0
fi

if ! nmcli connection show "$HOTSPOT_CONNECTION" >/dev/null 2>&1; then
    nmcli connection add type wifi ifname "$WIFI_IFACE" con-name "$HOTSPOT_CONNECTION" autoconnect no ssid "$HOTSPOT_SSID"
    nmcli connection modify "$HOTSPOT_CONNECTION" \
        802-11-wireless.mode ap \
        802-11-wireless.band bg \
        ipv4.method shared \
        ipv6.method ignore \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$HOTSPOT_PASSWORD"
fi

nmcli connection up "$HOTSPOT_CONNECTION"

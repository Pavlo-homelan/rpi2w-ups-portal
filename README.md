# ups-pi-node

`ups-pi-node` is a small web-managed UPS node for Raspberry Pi hardware. It monitors UPS state, exposes a local browser UI, manages Wi-Fi setup, and can raise a fallback hotspot when the device is not connected to a known network.

The project is designed for a Raspberry Pi based power node: the web app stays lightweight, and privileged system operations are delegated to a helper service instead of being executed directly by the site.

## Features

- UPS dashboard with voltage, current, battery level, AC status, CPU and RAM telemetry.
- Wi-Fi setup page with available network scan, password entry, and connection action.
- Fallback hotspot support through NetworkManager and systemd.
- System helper socket for privileged system tasks.
- Theme selector for dark and light UI.
- Interface language selector with Ukrainian and English only.
- UPS widget selector with built-in widget styles.
- Removable dashboard widgets for the main UPS card, CPU, RAM, and Wi-Fi status.
- Custom widget installation from ZIP packages with CSS, images, and fonts.
- Zabbix and Home Assistant integration metrics without Wi-Fi/portal-mode telemetry.
- Configuration through `/etc/ups-pi-node/main.conf`.

## Runtime Layout

Default install paths:

```text
/usr/lib/ups-pi-node
/etc/ups-pi-node/main.conf
/etc/default/ups-pi-node
/var/lib/ups-pi-node
/run/ups-pi-node/helper.sock
```

Application code is installed read-only under `/usr/lib/ups-pi-node`; runtime state such as the virtualenv, uploaded widget packages, and dashboard widget layout lives under `/var/lib/ups-pi-node`.

Main services:

```text
ups-pi-node.service
ups-pi-node-helper.service
ups-pi-node-hotspot-fallback.service
ups-pi-node-hotspot-fallback.timer
```

## Environment

Preferred environment variables use the `UPS_PI_NODE_` prefix:

```text
UPS_PI_NODE_SECRET_KEY
UPS_PI_NODE_NODE_ID
UPS_PI_NODE_INTEGRATIONS_TOKEN
UPS_PI_NODE_CONFIG_FILE
UPS_PI_NODE_WIDGETS_DIR
UPS_PI_NODE_DASHBOARD_WIDGETS_FILE
UPS_PI_NODE_AUTH_MODE
UPS_PI_NODE_PORTAL_USERNAME
UPS_PI_NODE_PORTAL_PASSWORD
UPS_PI_NODE_SYSTEM_HELPER_SOCKET
UPS_PI_NODE_WIFI_BACKEND
UPS_PI_NODE_WIFI_INTERFACE
UPS_PI_NODE_HOTSPOT_CONNECTION_NAME
UPS_PI_NODE_HOTSPOT_SSID
UPS_PI_NODE_HOTSPOT_PASSWORD
UPS_PI_NODE_HOTSPOT_ADDRESS
UPS_PI_NODE_PORTAL_MODE
UPS_PI_NODE_UPS_BACKEND
UPS_PI_NODE_AC_SENSOR_PIN
UPS_PI_NODE_BATTERY_EMPTY_VOLTAGE
UPS_PI_NODE_BATTERY_FULL_VOLTAGE
```

## Local Preview

For a local mock preview:

```bash
UPS_PI_NODE_SECRET_KEY=preview-secret \
UPS_PI_NODE_AUTH_MODE=mock \
UPS_PI_NODE_WIFI_BACKEND=mock \
UPS_PI_NODE_UPS_BACKEND=mock \
python wsgi.py
```

In the Codex preview environment this app has been run through WSL on:

```text
http://127.0.0.1:5000/login
```

Mock auth accepts any non-empty username and password.

## Widget Packages

Custom widgets are installed from ZIP packages. A minimal package:

```text
my-widget.zip
└── my-widget/
    ├── widget.json
    ├── style.css
    └── assets/
        └── display.woff2
```

See [docs/widgets.md](docs/widgets.md) for the widget package format, CSS variables, live fields, assets, fonts, and animation support.

## Integrations

Zabbix and Home Assistant receive only useful UPS/system metrics: battery, voltage, current, power, AC state, CPU, RAM, and app health. Wi-Fi SSID, hotspot state, and portal mode stay local to the UI.

See [docs/integrations.md](docs/integrations.md) for metric keys, Zabbix agent parameters, and Home Assistant discovery payloads.

## Stack

- Python / Flask
- Gunicorn + Nginx
- NetworkManager / nmcli
- systemd services and timers
- Optional INA219 UPS backend

## Status

The project is in active development. Current work is focused on the portal UI, helper isolation, deploy packaging, and custom widget support.

from collections import OrderedDict

from .system_stats import get_cpu_temp_value, get_ram_stats


BATTERY_STATUS_CODES = {
    "Critical": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Full": 4,
}

METRIC_DEFINITIONS = OrderedDict(
    {
        "app.health": {
            "name": "Application health",
            "unit": "",
            "kind": "numeric",
            "ha_platform": "binary_sensor",
            "ha_device_class": "connectivity",
        },
        "ups.ac_present": {
            "name": "AC present",
            "unit": "",
            "kind": "numeric",
            "ha_platform": "binary_sensor",
            "ha_device_class": "power",
        },
        "ups.battery.percent": {
            "name": "Battery percent",
            "unit": "%",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "battery",
            "ha_state_class": "measurement",
        },
        "ups.battery.status_code": {
            "name": "Battery status code",
            "unit": "",
            "kind": "numeric",
            "ha_platform": "sensor",
        },
        "ups.battery.charging": {
            "name": "Battery charging",
            "unit": "",
            "kind": "numeric",
            "ha_platform": "binary_sensor",
            "ha_device_class": "battery_charging",
        },
        "ups.battery.discharging": {
            "name": "Battery discharging",
            "unit": "",
            "kind": "numeric",
            "ha_platform": "binary_sensor",
        },
        "ups.voltage.v": {
            "name": "UPS voltage",
            "unit": "V",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "voltage",
            "ha_state_class": "measurement",
        },
        "ups.current.ma": {
            "name": "UPS current",
            "unit": "mA",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "current",
            "ha_state_class": "measurement",
        },
        "ups.current.abs_ma": {
            "name": "UPS absolute current",
            "unit": "mA",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "current",
            "ha_state_class": "measurement",
        },
        "ups.power.w": {
            "name": "UPS power",
            "unit": "W",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "power",
            "ha_state_class": "measurement",
        },
        "system.cpu.temp_c": {
            "name": "CPU temperature",
            "unit": "C",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_device_class": "temperature",
            "ha_state_class": "measurement",
        },
        "system.ram.used_mb": {
            "name": "RAM used",
            "unit": "MB",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_state_class": "measurement",
        },
        "system.ram.percent": {
            "name": "RAM percent",
            "unit": "%",
            "kind": "numeric",
            "ha_platform": "sensor",
            "ha_state_class": "measurement",
        },
    }
)


def build_metric_values(ups_snapshot):
    ram_stats = get_ram_stats() or {"used_mb": None, "percent": None}
    cpu_temp = get_cpu_temp_value()
    battery_direction = ups_snapshot.battery_direction

    return OrderedDict(
        {
            "app.health": 1,
            "ups.ac_present": 1 if ups_snapshot.mains_present else 0,
            "ups.battery.percent": ups_snapshot.battery_percent,
            "ups.battery.status_code": BATTERY_STATUS_CODES.get(ups_snapshot.battery_status, -1),
            "ups.battery.charging": 1 if battery_direction == "Charging" else 0,
            "ups.battery.discharging": 1 if battery_direction == "Discharging" else 0,
            "ups.voltage.v": round(ups_snapshot.bus_voltage, 3),
            "ups.current.ma": round(ups_snapshot.current_ma, 1),
            "ups.current.abs_ma": round(abs(ups_snapshot.current_ma), 1),
            "ups.power.w": round(ups_snapshot.power_w, 3),
            "system.cpu.temp_c": round(cpu_temp, 1) if cpu_temp is not None else None,
            "system.ram.used_mb": ram_stats["used_mb"],
            "system.ram.percent": ram_stats["percent"],
        }
    )


def build_metrics_payload(ups_snapshot, node_id):
    metrics = build_metric_values(ups_snapshot)
    return {
        "schema": "ups-pi-node.metrics.v1",
        "node": node_id,
        "metrics": metrics,
        "definitions": METRIC_DEFINITIONS,
    }


def metric_value_as_text(metrics, key):
    if key not in metrics:
        return None
    value = metrics[key]
    if value is None:
        return ""
    return str(value)


def build_zabbix_discovery_payload():
    return {
        "data": [
            {
                "{#METRIC_KEY}": key,
                "{#METRIC_NAME}": definition["name"],
                "{#METRIC_UNIT}": definition["unit"],
                "{#METRIC_KIND}": definition["kind"],
            }
            for key, definition in METRIC_DEFINITIONS.items()
        ]
    }


def build_home_assistant_payload(node_id, state_topic=None, availability_topic=None):
    state_topic = state_topic or f"{node_id}/state"
    availability_topic = availability_topic or f"{node_id}/availability"
    device = {
        "identifiers": [node_id],
        "name": node_id,
        "manufacturer": "ups-pi-node",
        "model": "UPS node",
    }

    discovery = []
    for key, definition in METRIC_DEFINITIONS.items():
        platform = definition.get("ha_platform", "sensor")
        object_id = key.replace(".", "_")
        payload = {
            "name": definition["name"],
            "unique_id": f"{node_id}_{object_id}",
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "value_template": "{{ value_json.metrics['" + key + "'] }}",
            "device": device,
        }
        if definition.get("unit"):
            payload["unit_of_measurement"] = definition["unit"]
        if definition.get("ha_device_class"):
            payload["device_class"] = definition["ha_device_class"]
        if definition.get("ha_state_class"):
            payload["state_class"] = definition["ha_state_class"]
        if platform == "binary_sensor":
            payload["payload_on"] = "1"
            payload["payload_off"] = "0"
        discovery.append(
            {
                "platform": platform,
                "object_id": object_id,
                "topic": f"homeassistant/{platform}/{node_id}/{object_id}/config",
                "payload": payload,
            }
        )

    return {
        "schema": "ups-pi-node.home-assistant.v1",
        "node": node_id,
        "state_topic": state_topic,
        "availability_topic": availability_topic,
        "discovery": discovery,
    }

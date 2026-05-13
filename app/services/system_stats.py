def get_cpu_temp_value():
    temp_path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(temp_path, "r", encoding="utf-8") as temp_file:
            return int(temp_file.read().strip()) / 1000
    except (OSError, ValueError):
        return None


def get_cpu_temp_label():
    value = get_cpu_temp_value()
    if value is None:
        return "--"
    return f"{value:.1f} C"


def get_ram_stats():
    meminfo = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as meminfo_file:
            for line in meminfo_file:
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])
    except (OSError, ValueError, IndexError):
        return None

    total = meminfo.get("MemTotal")
    available = meminfo.get("MemAvailable")
    if not total or available is None:
        return None

    used = max(0, total - available)
    return {
        "used_mb": round(used / 1024, 1),
        "percent": round((used / total) * 100, 1),
    }


def get_ram_label():
    stats = get_ram_stats()
    if not stats:
        return "--"
    return f"{stats['used_mb']:.0f} MB ({stats['percent']:.0f}%)"

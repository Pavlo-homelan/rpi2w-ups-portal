from dataclasses import dataclass, field
import subprocess


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    connected: bool = False

    @property
    def is_open(self):
        normalized = (self.security or "").strip().lower()
        return normalized in {"", "--", "open"}

    @property
    def security_label(self):
        return "Open" if self.is_open else self.security


@dataclass
class WifiScanResult:
    success: bool
    message: str
    networks: list[WifiNetwork] = field(default_factory=list)


@dataclass
class WifiActionResult:
    success: bool
    message: str


@dataclass
class WifiStatus:
    interface: str
    backend: str
    portal_mode: str
    connected_ssid: str | None
    connection_name: str | None
    ip_address: str | None
    hotspot_ssid: str
    hotspot_address: str
    state: str
    available: bool

    @property
    def portal_mode_label(self):
        labels = {
            "ap": "Fallback AP",
            "client": "Client Wi-Fi",
            "unknown": "Unknown",
        }
        return labels.get(self.portal_mode, self.portal_mode.title())


class WifiManager:
    def __init__(
        self,
        backend,
        interface,
        hotspot_connection_name,
        hotspot_ssid,
        hotspot_address,
        portal_mode="auto",
    ):
        self.backend = (backend or "mock").lower()
        self.interface = interface
        self.hotspot_connection_name = hotspot_connection_name
        self.hotspot_ssid = hotspot_ssid
        self.hotspot_address = hotspot_address
        self.portal_mode = portal_mode
        self._mock_connected_ssid = None

    @classmethod
    def from_config(cls, config):
        return cls(
            backend=config.get("WIFI_BACKEND", "mock"),
            interface=config.get("WIFI_INTERFACE", "wlan0"),
            hotspot_connection_name=config.get("HOTSPOT_CONNECTION_NAME", "rpi2w-hotspot"),
            hotspot_ssid=config.get("HOTSPOT_SSID", "rpi2w-setup"),
            hotspot_address=config.get("HOTSPOT_ADDRESS", "10.42.0.1"),
            portal_mode=config.get("PORTAL_MODE", "auto"),
        )

    def get_status(self):
        if self.backend == "nmcli":
            try:
                return self._get_nmcli_status()
            except RuntimeError:
                pass
        return self._get_mock_status()

    def scan_networks(self):
        if self.backend == "nmcli":
            try:
                return self._scan_nmcli_networks()
            except RuntimeError as exc:
                return WifiScanResult(False, str(exc), [])
        return self._scan_mock_networks()

    def connect(self, ssid, password="", hidden=False):
        if self.backend == "nmcli":
            try:
                return self._connect_nmcli(ssid=ssid, password=password, hidden=hidden)
            except RuntimeError as exc:
                return WifiActionResult(False, str(exc))
        return self._connect_mock(ssid=ssid, password=password, hidden=hidden)

    def _get_mock_status(self):
        portal_mode = "ap" if not self._mock_connected_ssid else "client"
        ip_address = self.hotspot_address if portal_mode == "ap" else "192.168.1.84"
        state = "connected" if self._mock_connected_ssid else "hotspot"
        return WifiStatus(
            interface=self.interface,
            backend="mock",
            portal_mode=portal_mode,
            connected_ssid=self._mock_connected_ssid,
            connection_name=self._mock_connected_ssid or self.hotspot_connection_name,
            ip_address=ip_address,
            hotspot_ssid=self.hotspot_ssid,
            hotspot_address=self.hotspot_address,
            state=state,
            available=True,
        )

    def _scan_mock_networks(self):
        connected = self._mock_connected_ssid
        networks = [
            WifiNetwork("Office UPS", 91, "WPA2", connected == "Office UPS"),
            WifiNetwork("Warehouse Mesh", 76, "WPA2 WPA3", connected == "Warehouse Mesh"),
            WifiNetwork("Field Service", 61, "WPA2", connected == "Field Service"),
            WifiNetwork("Guest Diagnostics", 48, "Open", connected == "Guest Diagnostics"),
        ]
        return WifiScanResult(
            True,
            "Сканирование завершено. Это mock-данные для интерфейса rpi2w.",
            networks,
        )

    def _connect_mock(self, ssid, password="", hidden=False):
        del password
        del hidden
        self._mock_connected_ssid = ssid
        return WifiActionResult(
            True,
            f"Mock-подключение к сети '{ssid}' выполнено. На устройстве тут будет вызов backend-команды.",
        )

    def _get_nmcli_status(self):
        status_output = self._run_command(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev", "status"]
        )
        interface_line = None
        for line in status_output.splitlines():
            device, dev_type, state, connection = self._split_nmcli_row(line, expected_parts=4)
            if device == self.interface and dev_type == "wifi":
                interface_line = {
                    "state": state,
                    "connection": connection if connection != "--" else None,
                }
                break

        if interface_line is None:
            raise RuntimeError(f"Интерфейс Wi-Fi '{self.interface}' не найден через nmcli.")

        ip_output = self._run_command(["nmcli", "-t", "-f", "IP4.ADDRESS", "dev", "show", self.interface])
        ip_address = None
        for line in ip_output.splitlines():
            if line.startswith("IP4.ADDRESS"):
                _, value = line.split(":", 1)
                ip_address = value.split("/", 1)[0]
                break

        portal_mode = self._resolve_portal_mode(interface_line["state"], interface_line["connection"])
        return WifiStatus(
            interface=self.interface,
            backend="nmcli",
            portal_mode=portal_mode,
            connected_ssid=interface_line["connection"] if portal_mode == "client" else None,
            connection_name=interface_line["connection"],
            ip_address=ip_address,
            hotspot_ssid=self.hotspot_ssid,
            hotspot_address=self.hotspot_address,
            state=interface_line["state"],
            available=True,
        )

    def _scan_nmcli_networks(self):
        output = self._run_command(
            [
                "nmcli",
                "-t",
                "-f",
                "IN-USE,SSID,SIGNAL,SECURITY",
                "dev",
                "wifi",
                "list",
                "ifname",
                self.interface,
                "--rescan",
                "yes",
            ]
        )

        discovered = {}
        for line in output.splitlines():
            if not line.strip():
                continue
            in_use, ssid, signal, security = self._split_nmcli_row(line, expected_parts=4)
            ssid = ssid.strip() or "Скрытая сеть"
            signal_value = int(signal) if signal.isdigit() else 0
            connected = in_use.strip() == "*"
            existing = discovered.get(ssid)
            network = WifiNetwork(ssid, signal_value, security or "Open", connected)
            if existing is None or network.signal > existing.signal or network.connected:
                discovered[ssid] = network

        networks = sorted(discovered.values(), key=lambda item: (-item.connected, -item.signal, item.ssid.lower()))
        return WifiScanResult(True, "Сканирование Wi-Fi выполнено через nmcli.", networks)

    def _connect_nmcli(self, ssid, password="", hidden=False):
        command = ["nmcli", "dev", "wifi", "connect", ssid, "ifname", self.interface]
        if password:
            command.extend(["password", password])
        if hidden:
            command.extend(["hidden", "yes"])

        output = self._run_command(command)
        message = output.strip() or f"Команда подключения к сети '{ssid}' выполнена."
        return WifiActionResult(True, message)

    def _resolve_portal_mode(self, state, connection_name):
        if self.portal_mode in {"ap", "client"}:
            return self.portal_mode
        if connection_name and connection_name == self.hotspot_connection_name:
            return "ap"
        if state == "connected":
            return "client"
        return "ap"

    def _run_command(self, command):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=20,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Команда backend для работы с Wi-Fi не найдена.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Команда backend для работы с Wi-Fi превысила лимит ожидания.") from exc

        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip() or "Неизвестная ошибка"
            raise RuntimeError(f"Wi-Fi backend вернул ошибку: {details}")

        return completed.stdout

    def _split_nmcli_row(self, value, expected_parts):
        parts = []
        current = []
        escaped = False

        for character in value:
            if escaped:
                current.append(character)
                escaped = False
                continue

            if character == "\\":
                escaped = True
                continue

            if character == ":" and len(parts) < expected_parts - 1:
                parts.append("".join(current))
                current = []
                continue

            current.append(character)

        parts.append("".join(current))
        while len(parts) < expected_parts:
            parts.append("")
        return parts[:expected_parts]

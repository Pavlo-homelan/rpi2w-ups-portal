import hmac
from dataclasses import dataclass

try:
    import pam  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    pam = None


@dataclass
class AuthResult:
    success: bool
    message: str


class SystemAuthService:
    def __init__(self, mode, portal_username, portal_password):
        self.mode = (mode or "mock").lower()
        self.portal_username = portal_username
        self.portal_password = portal_password

    @classmethod
    def from_config(cls, config):
        return cls(
            mode=config.get("AUTH_MODE", "mock"),
            portal_username=config.get("PORTAL_USERNAME", "rpi2w-admin"),
            portal_password=config.get("PORTAL_PASSWORD", "rpi2w-demo"),
        )

    def metadata(self):
        labels = {
            "mock": "Mock auth",
            "env": "Env credentials",
            "pam": "PAM system auth",
        }
        descriptions = {
            "mock": "Для разработки: пропускает любой непустой логин и пароль.",
            "env": "Сверяет логин и пароль с переменными окружения портала.",
            "pam": "Проверяет системного пользователя Linux через PAM.",
        }
        return {
            "mode": self.mode,
            "label": labels.get(self.mode, self.mode),
            "description": descriptions.get(self.mode, "Режим аутентификации не описан."),
            "production_ready": self.mode in {"env", "pam"},
        }

    def authenticate(self, username, password):
        if self.mode == "pam":
            return self._authenticate_pam(username, password)
        if self.mode == "env":
            return self._authenticate_env(username, password)
        return self._authenticate_mock(username, password)

    def _authenticate_mock(self, username, password):
        if username and password:
            return AuthResult(
                True,
                "Вход выполнен в mock-режиме. Для реального устройства переключите auth на PAM или env.",
            )
        return AuthResult(False, "Укажите логин и пароль.")

    def _authenticate_env(self, username, password):
        valid_username = hmac.compare_digest(username, self.portal_username)
        valid_password = hmac.compare_digest(password, self.portal_password)
        if valid_username and valid_password:
            return AuthResult(True, "Вход выполнен. Доступ к управлению Wi-Fi открыт.")
        return AuthResult(False, "Неверные учётные данные портала rpi2w.")

    def _authenticate_pam(self, username, password):
        if pam is None:
            return AuthResult(
                False,
                "PAM-модуль не установлен. Подключите python-pam или переключите портал на env-auth.",
            )

        authenticator = pam.pam()
        if authenticator.authenticate(username, password):
            return AuthResult(True, "Системный пользователь подтверждён через PAM.")

        return AuthResult(False, "PAM отклонил логин или пароль системного пользователя.")

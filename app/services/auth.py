import hmac
from dataclasses import dataclass, field

try:
    import pam  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    pam = None


@dataclass
class AuthResult:
    success: bool
    message_key: str
    message_params: dict = field(default_factory=dict)


class SystemAuthService:
    def __init__(self, mode, portal_username, portal_password):
        self.mode = (mode or "mock").lower()
        self.portal_username = portal_username
        self.portal_password = portal_password

    @classmethod
    def from_config(cls, config):
        return cls(
            mode=config.get("AUTH_MODE", "mock"),
            portal_username=config.get("PORTAL_USERNAME", "ups-pi-admin"),
            portal_password=config.get("PORTAL_PASSWORD", "ups-pi-demo"),
        )

    def metadata(self):
        labels = {
            "mock": "Mock auth",
            "env": "Env credentials",
            "pam": "PAM system auth",
        }
        descriptions = {
            "mock": "Accepts any non-empty login and password for development.",
            "env": "Checks the login and password against portal environment variables.",
            "pam": "Checks the Linux system user through PAM.",
        }
        return {
            "mode": self.mode,
            "label": labels.get(self.mode, self.mode),
            "description": descriptions.get(self.mode, "Authentication mode is not described."),
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
            return AuthResult(True, "auth.mock_success")
        return AuthResult(False, "auth.missing_credentials")

    def _authenticate_env(self, username, password):
        valid_username = hmac.compare_digest(username, self.portal_username)
        valid_password = hmac.compare_digest(password, self.portal_password)
        if valid_username and valid_password:
            return AuthResult(True, "auth.env_success")
        return AuthResult(False, "auth.env_failure")

    def _authenticate_pam(self, username, password):
        if pam is None:
            return AuthResult(False, "auth.pam_missing")

        authenticator = pam.pam()
        if authenticator.authenticate(username, password):
            return AuthResult(True, "auth.pam_success")

        return AuthResult(False, "auth.pam_failure")

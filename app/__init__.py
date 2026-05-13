from flask import Flask

from config import Config
from .routes import main
from .services.auth import SystemAuthService
from .services.config import ConfigManager
from .services.ups import UpsManager
from .services.wifi import WifiManager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.extensions["rpi2w_config"] = ConfigManager.from_config(app.config)
    app.extensions["rpi2w_auth"] = SystemAuthService.from_config(app.config)
    app.extensions["rpi2w_ups"] = UpsManager.from_config(app.config)
    app.extensions["rpi2w_wifi"] = WifiManager.from_config(app.config)

    app.register_blueprint(main)
    return app

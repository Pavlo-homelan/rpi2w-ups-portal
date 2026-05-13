from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


main = Blueprint("main", __name__)


def get_auth_service():
    return current_app.extensions["rpi2w_auth"]


def get_ups_manager():
    return current_app.extensions["rpi2w_ups"]


def get_wifi_manager():
    return current_app.extensions["rpi2w_wifi"]


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("authenticated"):
            flash("Сначала выполните вход в портал управления rpi2w.", "error")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped_view


def build_portal_context(scan_networks=True):
    auth_service = get_auth_service()
    ups_manager = get_ups_manager()
    wifi_manager = get_wifi_manager()
    scan_result = wifi_manager.scan_networks() if scan_networks else None

    return {
        "auth_meta": auth_service.metadata(),
        "ups_snapshot": ups_manager.get_snapshot(),
        "portal_status": wifi_manager.get_status(),
        "scan_result": scan_result,
        "current_user": session.get("username"),
    }


def render_login_page(form_data=None):
    return render_template(
        "login.html",
        form_data=form_data or {"username": "", "node_name": "rpi2w-core-01"},
    )


@main.get("/")
def index():
    if session.get("authenticated"):
        return redirect(url_for("main.dashboard"))
    return render_login_page()


@main.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("main.dashboard"))

    auth_service = get_auth_service()
    form_data = {"username": "", "node_name": "rpi2w-core-01"}

    if request.method == "POST":
        form_data["username"] = request.form.get("username", "").strip()
        form_data["node_name"] = request.form.get("node_name", "").strip() or "rpi2w-core-01"
        password = request.form.get("password", "")

        if not form_data["username"] or not password:
            flash("Укажите системный логин и пароль пользователя rpi2w.", "error")
        else:
            result = auth_service.authenticate(form_data["username"], password)
            if result.success:
                session.clear()
                session["authenticated"] = True
                session["username"] = form_data["username"]
                session["node_name"] = form_data["node_name"]
                flash(result.message, "success")
                return redirect(url_for("main.dashboard"))
            flash(result.message, "error")

    return render_login_page(form_data)


@main.post("/logout")
def logout():
    session.clear()
    flash("Сессия rpi2w завершена.", "info")
    return redirect(url_for("main.login"))


@main.get("/wifi")
@login_required
def wifi_dashboard():
    context = build_portal_context(scan_networks=True)
    return render_template("wifi.html", **context)


@main.get("/dashboard")
@login_required
def dashboard():
    context = build_portal_context(scan_networks=False)
    return render_template("index.html", **context)


@main.post("/wifi/connect")
@login_required
def connect_wifi():
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    hidden = request.form.get("hidden") == "1"

    if not ssid:
        flash("Укажите SSID сети, к которой нужно подключиться.", "error")
        return redirect(url_for("main.wifi_dashboard"))

    result = get_wifi_manager().connect(ssid=ssid, password=password, hidden=hidden)
    flash(result.message, "success" if result.success else "error")
    return redirect(url_for("main.wifi_dashboard"))


@main.get("/health")
@login_required
def health():
    ups_snapshot = get_ups_manager().get_snapshot()
    portal_status = get_wifi_manager().get_status()
    return {
        "status": "ok",
        "portal_mode": portal_status.portal_mode,
        "wifi_backend": portal_status.backend,
        "interface": portal_status.interface,
        "mains_present": ups_snapshot.mains_present,
        "ups_mode": ups_snapshot.mode_label,
        "load_source": ups_snapshot.load_source,
        "battery_percent": ups_snapshot.battery_percent,
        "battery_status": ups_snapshot.battery_status,
    }, 200

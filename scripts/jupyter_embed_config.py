import os

try:
    get_config  # type: ignore[name-defined]
except NameError:
    from types import SimpleNamespace

    class _DummyConfig(SimpleNamespace):
        def __getattr__(self, name):
            value = SimpleNamespace()
            setattr(self, name, value)
            return value

    def get_config():
        return _DummyConfig()

c = get_config()  # noqa: F821

# Embed-safe defaults for local development with Audela ML Studio.
AUDELA_ORIGIN = os.environ.get("AUDELA_ORIGIN", "http://127.0.0.1:5000").rstrip("/")
EXTRA_ANCESTORS = os.environ.get("JUPYTER_EXTRA_FRAME_ANCESTORS", "http://localhost:5000").strip()

frame_ancestors = ["'self'", AUDELA_ORIGIN]
if EXTRA_ANCESTORS:
    for raw in EXTRA_ANCESTORS.split(","):
        item = raw.strip()
        if item:
            frame_ancestors.append(item)

c.ServerApp.open_browser = False
c.ServerApp.allow_remote_access = True
c.ServerApp.allow_origin = AUDELA_ORIGIN
c.ServerApp.ip = os.environ.get("JUPYTER_BIND_IP", "127.0.0.1")
c.ServerApp.port = int(os.environ.get("JUPYTER_PORT", "8888"))

# Local embedded mode: disable auth prompt by default on loopback.
require_token = os.environ.get("JUPYTER_REQUIRE_TOKEN", "0").strip().lower() in {"1", "true", "yes", "on"}
if require_token:
    c.ServerApp.token = os.environ.get("JUPYTER_TOKEN", "").strip()
else:
    c.ServerApp.token = ""
    c.ServerApp.password = ""

# Jupyter blocks iframe by default. Allow Audela origin explicitly.
c.ServerApp.tornado_settings = {
    "headers": {
        "Content-Security-Policy": "frame-ancestors " + " ".join(frame_ancestors) + ";",
    }
}

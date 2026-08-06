from __future__ import annotations

import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app.web import create_app

TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"


@pytest.fixture(scope="session")
def live_server_url():
    app = create_app(templates_dir=TEMPLATES)
    app.config["TESTING"] = True
    server = make_server("127.0.0.1", 0, app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()

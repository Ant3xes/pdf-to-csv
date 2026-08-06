from __future__ import annotations

import threading

from werkzeug.serving import BaseWSGIServer, make_server

from app.runtime_paths import configure_runtime_paths
from app.web import create_app

APP_TITLE = "Convertisseur Factures"
DEFAULT_HOST = "127.0.0.1"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800


def start_server(
    host: str = DEFAULT_HOST,
    port: int = 0,
) -> tuple[BaseWSGIServer, str, threading.Thread]:
    configure_runtime_paths()
    app = create_app()
    server = make_server(host, port, app)
    url = f"http://{host}:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url, thread


def stop_server(server: BaseWSGIServer) -> None:
    server.shutdown()


def run_desktop_app() -> None:
    import webview

    server, url, _thread = start_server()
    try:
        webview.create_window(
            APP_TITLE,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
        )
        webview.start()
    finally:
        stop_server(server)


def main() -> None:
    run_desktop_app()


if __name__ == "__main__":
    main()

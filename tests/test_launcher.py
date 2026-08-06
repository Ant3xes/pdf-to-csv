from __future__ import annotations

import urllib.request

from app.launcher import WINDOW_HEIGHT, WINDOW_WIDTH, start_server, stop_server


def test_launcher_window_size_accommodates_split_preview():
    """Fenêtre desktop assez large pour le split aperçu (#50)."""
    assert WINDOW_WIDTH >= 1200
    assert WINDOW_HEIGHT >= 700


def test_launcher_starts_flask_and_serves_home():
    server, url, _thread = start_server()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            body = response.read().decode()
            assert 'id="drop-zone"' in body
            assert "Convertisseur de factures" in body
    finally:
        stop_server(server)

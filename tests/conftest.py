from __future__ import annotations

import inspect
import re
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app.web import create_app

TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"
ROOT = Path(__file__).resolve().parents[1]

# Corpus de factures réelles : privé, jamais versionné ni fourni (voir README.md).
# Les tests qui le lisent (constantes CORPUS / CORPUS_2) sont ignorés s'il est absent.
CORPUS_DIRS = {"CORPUS": ROOT / "private_corpus", "CORPUS_2": ROOT / "private_corpus_2"}


def pytest_collection_modifyitems(config, items):
    for item in items:
        func = getattr(item, "function", None)
        if func is None:
            continue
        try:
            source = inspect.getsource(func)
        except (OSError, TypeError):
            continue
        for name, path in CORPUS_DIRS.items():
            if re.search(rf"\b{name}\b", source) and not path.is_dir():
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"corpus privé absent ({path.name}/) : non fourni avec le dépôt"
                    )
                )
                break


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

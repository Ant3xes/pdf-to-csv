from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from app.lot import process_lot

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_TEMPLATES_DIR = _PACKAGE_DIR.parent / "invoice_templates"


def create_app(*, templates_dir: Path | str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_PACKAGE_DIR / "templates"),
        static_folder=str(_PACKAGE_DIR / "static"),
    )
    app.config["INVOICE_TEMPLATES_DIR"] = Path(
        templates_dir if templates_dir is not None else _DEFAULT_TEMPLATES_DIR
    )
    app.config["UPLOAD_FOLDER"] = Path(tempfile.gettempdir()) / "pdf-to-csv-uploads"

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/lot")
    def api_lot():
        uploads = request.files.getlist("files")
        if not uploads or all(not (s.filename or "").strip() for s in uploads):
            return jsonify({"error": "Aucun fichier reçu."}), 400

        upload_root = Path(app.config["UPLOAD_FOLDER"])
        upload_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(dir=upload_root))

        try:
            pdf_paths: list[Path] = []
            for storage in uploads:
                filename = Path(storage.filename or "").name
                if not filename:
                    continue
                if not filename.lower().endswith(".pdf"):
                    return (
                        jsonify(
                            {
                                "error": (
                                    f"Le fichier «{filename}» n'est pas un PDF "
                                    "exploitable. Seuls les fichiers .pdf sont acceptés."
                                )
                            }
                        ),
                        400,
                    )
                dest = work_dir / filename
                storage.save(dest)
                pdf_paths.append(dest)

            if not pdf_paths:
                return jsonify({"error": "Aucun fichier reçu."}), 400

            lignes = process_lot(pdf_paths, app.config["INVOICE_TEMPLATES_DIR"])
            return jsonify({"lignes": [asdict(ligne) for ligne in lignes]})
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

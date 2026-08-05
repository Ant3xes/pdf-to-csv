from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from app.csv_export import export_csv
from app.lot import is_supported_document, process_lot, supported_document_formats_label
from app.models import TYPES_DOCUMENT, LigneFacture

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
            document_paths: list[Path] = []
            for storage in uploads:
                filename = Path(storage.filename or "").name
                if not filename:
                    continue
                if not is_supported_document(filename):
                    return (
                        jsonify(
                            {
                                "error": (
                                    f"Le fichier «{filename}» n'est pas un format "
                                    "exploitable. "
                                    f"Formats acceptés : {supported_document_formats_label()}."
                                )
                            }
                        ),
                        400,
                    )
                dest = work_dir / filename
                storage.save(dest)
                document_paths.append(dest)

            if not document_paths:
                return jsonify({"error": "Aucun fichier reçu."}), 400

            lignes = process_lot(document_paths, app.config["INVOICE_TEMPLATES_DIR"])
            return jsonify({"lignes": [asdict(ligne) for ligne in lignes]})
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @app.post("/api/export")
    def api_export():
        payload = request.get_json(silent=True) or {}
        raw_lignes = payload.get("lignes")
        if not isinstance(raw_lignes, list) or len(raw_lignes) == 0:
            return jsonify({"error": "Aucune ligne à exporter."}), 400

        lignes: list[LigneFacture] = []
        for raw in raw_lignes:
            if (
                not isinstance(raw, dict)
                or "fichier" not in raw
                or "statut" not in raw
                or "type_document" not in raw
            ):
                return jsonify({"error": "Ligne de facture invalide."}), 400
            type_document = str(raw["type_document"])
            if type_document not in TYPES_DOCUMENT:
                return jsonify({"error": "Type de document invalide."}), 400
            lignes.append(
                LigneFacture(
                    fichier=str(raw["fichier"]),
                    emetteur=raw.get("emetteur"),
                    date=raw.get("date"),
                    montant_ht=raw.get("montant_ht"),
                    statut=str(raw["statut"]),
                    type_document=type_document,
                )
            )

        csv_body = export_csv(lignes)
        return Response(
            csv_body,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="lot.csv"',
            },
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

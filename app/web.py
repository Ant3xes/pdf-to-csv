from __future__ import annotations

import shutil
import tempfile
import traceback
from pathlib import Path

from flask import Flask, Response, current_app, jsonify, render_template, request

from app.amounts import MontantHt
from app.csv_export import export_csv, export_csv_agrege, valider_export
from app.diagnostics import ACTION_KINDS, DiagnosticJournal
from app.lot import is_supported_document, process_lot, supported_document_formats_label
from app.models import TYPES_DOCUMENT, LigneFacture

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_TEMPLATES_DIR = _PACKAGE_DIR.parent / "invoice_templates"


def _journal() -> DiagnosticJournal:
    return current_app.extensions["diagnostic_journal"]


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
    app.extensions["diagnostic_journal"] = DiagnosticJournal()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/journal")
    def api_journal():
        journal = _journal()
        if journal.is_empty():
            return jsonify({"error": "Aucun journal à exporter."}), 404
        return Response(
            journal.export_text(),
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="journal.txt"',
            },
        )

    @app.post("/api/journal/reset")
    def api_journal_reset():
        _journal().clear()
        return Response(status=204)

    @app.post("/api/journal/events")
    def api_journal_events():
        payload = request.get_json(silent=True) or {}
        raw_events = payload.get("events")
        if not isinstance(raw_events, list) or len(raw_events) == 0:
            return jsonify({"error": "Aucun événement à enregistrer."}), 400

        parsed: list[tuple[str, dict]] = []
        for raw in raw_events:
            if not isinstance(raw, dict) or "action" not in raw:
                return jsonify({"error": "Événement de journal invalide."}), 400
            action = str(raw["action"])
            if action not in ACTION_KINDS:
                return jsonify({"error": f"Action inconnue : {action}."}), 400
            fields = {
                key: value
                for key, value in raw.items()
                if key != "action" and value is not None
            }
            parsed.append((action, fields))

        journal = _journal()
        for action, fields in parsed:
            journal.record_action(action, fields)
        return Response(status=204)

    @app.post("/api/lot")
    def api_lot():
        uploads = request.files.getlist("files")
        if not uploads or all(not (s.filename or "").strip() for s in uploads):
            return jsonify({"error": "Aucun fichier reçu."}), 400

        upload_root = Path(app.config["UPLOAD_FOLDER"])
        upload_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(dir=upload_root))

        try:
            journal = _journal()

            document_paths: list[Path] = []
            warnings: list[str] = []
            for storage in uploads:
                filename = Path(storage.filename or "").name
                if not filename:
                    continue
                if not is_supported_document(filename):
                    warnings.append(
                        f"Le fichier «{filename}» n'est pas un format "
                        "exploitable. "
                        f"Formats acceptés : {supported_document_formats_label()}."
                    )
                    continue
                dest = work_dir / filename
                storage.save(dest)
                document_paths.append(dest)

            if not document_paths:
                if warnings:
                    return jsonify({"error": " ".join(warnings)}), 400
                return jsonify({"error": "Aucun fichier reçu."}), 400

            try:
                lignes = process_lot(
                    document_paths,
                    app.config["INVOICE_TEMPLATES_DIR"],
                    journal=journal,
                )
            except Exception as exc:
                journal.record(
                    f"EXCEPTION type={type(exc).__name__} message={exc}"
                )
                for line in traceback.format_exc().strip().splitlines():
                    journal.record(f"traceback {line}")
                return jsonify(
                    {
                        "error": (
                            "Échec technique du traitement du lot. "
                            "Exportez le journal pour le diagnostic."
                        ),
                        "error_detail": f"{type(exc).__name__}: {exc}",
                        "journal_disponible": not journal.is_empty(),
                    }
                ), 500
            return jsonify(
                {
                    "lignes": [ligne.to_api_dict() for ligne in lignes],
                    "warnings": warnings,
                    "journal_disponible": not journal.is_empty(),
                }
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @app.post("/api/export")
    def api_export():
        # La vérité runtime à l'export est l'état client (corrections UI locales).
        payload = request.get_json(silent=True) or {}
        raw_lignes = payload.get("lignes")
        if not isinstance(raw_lignes, list) or len(raw_lignes) == 0:
            return jsonify({"error": "Aucune ligne à exporter."}), 400

        mode = payload.get("mode", "detail")
        if mode not in ("detail", "agrege"):
            return jsonify({"error": "Mode d'export invalide."}), 400

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
                    montant_ht=MontantHt.parse_fr(raw.get("montant_ht")),
                    statut=str(raw["statut"]),
                    type_document=type_document,
                )
            )

        erreur = valider_export(lignes)
        if erreur:
            return jsonify({"error": erreur}), 400

        if mode == "agrege":
            csv_body = export_csv_agrege(lignes)
            filename = "lot-groupe.csv"
        else:
            csv_body = export_csv(lignes)
            filename = "lot-detail.csv"
        return Response(
            csv_body,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

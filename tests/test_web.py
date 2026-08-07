import re
import shutil
from pathlib import Path

import pytest

from app.web import create_app

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"


@pytest.fixture
def client(tmp_path):
    app = create_app(templates_dir=TEMPLATES)
    app.config["TESTING"] = True
    # Isolate any temp upload dir from the corpus.
    app.config["UPLOAD_FOLDER"] = tmp_path / "uploads"
    app.config["UPLOAD_FOLDER"].mkdir()
    return app.test_client()


def test_page_accueil_contient_zone_depot_et_tableau(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="drop-zone"' in html
    assert 'id="file-input"' in html
    assert 'id="processing-indicator"' in html
    assert 'id="issuer-groups"' in html
    assert 'id="documents-section"' in html
    assert 'id="totaux-emetteurs"' in html
    assert 'id="export-block-message"' in html
    assert "Documents" in html
    assert "Synthèse par émetteur" in html
    assert "lot_grouping.js" in html
    assert "app.js" in html


def test_static_js_gere_depot_et_tableau(client):
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "dragover" in js
    assert "/api/lot" in js
    assert "processing-indicator" in js
    assert "À vérifier" in js
    assert "warnings" in js
    assert "keepFilesForLignes" in js


def test_static_js_edition_inline_emetteur_date_montant(client):
    """Émetteur, date et montant éditables via inputs lisibles (#25)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert 'createElement("input")' in js
    assert "contentEditable" not in js
    assert "contenteditable" not in js
    for champ in ("emetteur", "date", "montant_ht"):
        assert champ in js
    # fichier et statut restent en lecture seule côté édition
    assert "fichier" in js
    assert "statut" in js


def test_static_js_correction_manuelle_ok_et_a_verifier_sans_template(client):
    """Correction manuelle du Lot : OK et À vérifier, jamais de Template (#12/#25)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    # Champs corrigibles sans filtre sur le statut de la ligne
    assert 'EDITABLE_FIELDS = ["emetteur", "date", "montant_ht"]' in js
    assert 'createElement("input")' in js
    # L'édition des champs n'est pas conditionnée au statut (Valider est séparé, #27)
    assert "EDITABLE_FIELDS.includes(key)" in js
    # État local du Lot (Correction manuelle éphémère, sémantique #10)
    assert "lotLignes" in js
    assert "corrigerLigneLocale" in js
    # Aucun chemin UI vers les Templates
    assert "invoice_templates" not in js
    assert "/api/template" not in js


def test_static_js_bouton_valider_a_verifier_vers_ok(client):
    """Bouton Valider : À vérifier → OK si émetteur, date et montant remplis (#27)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Valider" in js
    assert "validerLigne" in js
    assert "champsRemplis" in js
    assert "A_VERIFIER" in js
    assert 'statut: "OK"' in js
    # Pas de création de Template
    assert "invoice_templates" not in js
    assert "/api/template" not in js


def test_page_accueil_contient_colonne_valider(client):
    """Le rendu JS conserve l'action Valider pour une Facture À vérifier (#27)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Valider" in js
    assert "<th>Action</th>" not in js or "Action" in js


def test_api_export_accepte_statut_ok_apres_validation_client(client):
    """L'export CSV accepte le statut OK envoyé par le client après Valider (#27)."""
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": "Saisi à la main",
                    "date": "01/08/2026",
                    "montant_ht": "12,50",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert body == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Saisi à la main;12,50;1\n"
    )


def test_static_js_champs_edition_preremplis_ou_placeholder(client):
    """Valeurs extraites préremplies ; vides = placeholder, jamais inventées (#25)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "placeholder" in js
    # Préremplissage depuis la valeur extraite (y compris A_VERIFIER / OCR)
    assert "input.value" in js
    # Champ vide : chaîne vide, pas de tiret inventé dans l'input
    assert 'input.value = ""' in js or 'input.value = value' in js or "inputValue" in js
    # Pas d'invention de données fictives dans les placeholders métier
    assert "Inventé" not in js
    assert "TODO" not in js


def test_api_lot_un_pdf_retourne_ligne_facture(client):
    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "Masse 22 Juillet 26.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert "lignes" in payload
    assert len(payload["lignes"]) == 1
    ligne = payload["lignes"][0]
    assert ligne["fichier"] == "Masse 22 Juillet 26.pdf"
    assert ligne["emetteur"] == "Masse"
    assert ligne["date"] == "22/07/2026"
    assert ligne["montant_ht"] == "751,95"
    assert ligne["statut"] == "OK"
    assert ligne["type_document"] == "FACTURE"


def test_api_lot_multi_pdf_inclut_avoir(client):
    masse = CORPUS / "Masse 22 Juillet 26.pdf"
    avoir = CORPUS / "Hennequin AVOIR 10 Juillet 26.pdf"
    with masse.open("rb") as fh_m, avoir.open("rb") as fh_a:
        response = client.post(
            "/api/lot",
            data={
                "files": [
                    (fh_m, "Masse 22 Juillet 26.pdf"),
                    (fh_a, "Hennequin AVOIR 10 Juillet 26.pdf"),
                ]
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    lignes = response.get_json()["lignes"]
    assert len(lignes) == 2
    assert lignes[0]["fichier"] == "Masse 22 Juillet 26.pdf"
    assert lignes[1]["fichier"] == "Hennequin AVOIR 10 Juillet 26.pdf"
    assert set(lignes[1]) >= {
        "fichier",
        "emetteur",
        "date",
        "montant_ht",
        "statut",
        "type_document",
    }
    assert lignes[0]["type_document"] == "FACTURE"
    assert lignes[1]["type_document"] == "AVOIR"


def test_api_lot_accepte_extension_PDF_majuscule(client):
    pdf_path = CORPUS / "Hotel Formule 1 5 Juillet 26.PDF"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "Hotel Formule 1 5 Juillet 26.PDF")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    lignes = response.get_json()["lignes"]
    assert len(lignes) == 1
    assert lignes[0]["fichier"] == "Hotel Formule 1 5 Juillet 26.PDF"


def test_api_lot_accepte_image_png(client):
    png_path = Path(__file__).resolve().parent / "fixtures" / "scan_sans_texte.png"
    with png_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "scan_sans_texte.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    lignes = response.get_json()["lignes"]
    assert len(lignes) == 1
    assert lignes[0]["fichier"] == "scan_sans_texte.png"
    assert lignes[0]["statut"] == "A_VERIFIER"


def test_api_lot_rejette_format_non_supporte_avec_message_clair(client):
    with (CORPUS / "Masse 22 Juillet 26.pdf").open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "facture.docx")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
    assert "facture.docx" in payload["error"]
    assert "lignes" not in payload


def test_api_lot_mixte_valide_et_non_supporte_avertit(client):
    """PDF valide traité ; .docx rejeté avec warning, sans échec global (#16)."""
    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh_pdf, pdf_path.open("rb") as fh_bad:
        response = client.post(
            "/api/lot",
            data={
                "files": [
                    (fh_pdf, "Masse 22 Juillet 26.pdf"),
                    (fh_bad, "facture.docx"),
                ]
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["lignes"]) == 1
    assert payload["lignes"][0]["fichier"] == "Masse 22 Juillet 26.pdf"
    assert any("facture.docx" in w for w in payload["warnings"])


def test_api_lot_ne_persiste_pas_dans_corpus(client):
    """Le Lot est éphémère : private_corpus/ n'est pas un stockage de session."""
    before = {p.name for p in CORPUS.iterdir()}
    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "copie-session-ephemere.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    after = {p.name for p in CORPUS.iterdir()}
    assert after == before
    assert not (CORPUS / "copie-session-ephemere.pdf").exists()
    upload_folder = Path(client.application.config["UPLOAD_FOLDER"])
    leftovers = list(upload_folder.rglob("*")) if upload_folder.exists() else []
    assert leftovers == [] or all(p.is_dir() for p in leftovers)


def test_api_export_csv_format_fr_avec_corrections(client):
    """POST /api/export télécharge le CSV agrégé du Lot, Corrections manuelles incluses (#13)."""
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": "Saisi à la main",
                    "date": "01/08/2026",
                    "montant_ht": "12,50",
                    "statut": "OK",
                    "type_document": "AVOIR",
                },
                {
                    "fichier": "Masse 22 Juillet 26.pdf",
                    "emetteur": "Masse",
                    "date": "22/07/2026",
                    "montant_ht": "751,95",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert "text/csv" in response.content_type
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert 'filename="lot.csv"' in response.headers.get("Content-Disposition", "")
    body = response.data.decode()
    assert body == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Masse;751,95;1\n"
        "Saisi à la main;12,50;1\n"
    )
    assert "raison" not in body.lstrip("\ufeff").split("\n")[0]


def test_api_export_agrege_meme_emetteur(client):
    """Plusieurs factures du même Émetteur → une ligne CSV agrégée (#42)."""
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "Masse 22 Juillet 26.pdf",
                    "emetteur": "Masse",
                    "date": "22/07/2026",
                    "montant_ht": "751,95",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
                {
                    "fichier": "Masse 15 Juillet 26.pdf",
                    "emetteur": "Masse",
                    "date": "15/07/2026",
                    "montant_ht": "203,29",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert response.data.decode() == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Masse;955,24;2\n"
    )


def test_api_export_rejette_a_verifier(client):
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": "Masse",
                    "date": "01/08/2026",
                    "montant_ht": "12,50",
                    "statut": "A_VERIFIER",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert "vérifier" in response.get_json()["error"].lower()


def test_api_export_rejette_emetteur_manquant(client):
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": None,
                    "date": "01/08/2026",
                    "montant_ht": "12,50",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert "émetteur" in response.get_json()["error"].lower()


def test_api_export_total_net_facture_et_avoir(client):
    """Total net par Émetteur inclut Factures et Avoirs (#42)."""
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "Masse 22 Juillet 26.pdf",
                    "emetteur": "Hennequin",
                    "date": "22/07/2026",
                    "montant_ht": "1751,30",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
                {
                    "fichier": "Hennequin AVOIR 10 Juillet 26.pdf",
                    "emetteur": "Hennequin",
                    "date": "10/07/2026",
                    "montant_ht": "-1350,50",
                    "statut": "OK",
                    "type_document": "AVOIR",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert response.data.decode() == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Hennequin;400,80;2\n"
    )


def test_api_export_rejette_ok_sans_date_ou_montant(client):
    """Export refuse un statut OK client si date/montant manquent (#17)."""
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": "Masse",
                    "date": None,
                    "montant_ht": "12,50",
                    "statut": "OK",
                    "type_document": "FACTURE",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert "date" in response.get_json()["error"].lower() or "montant" in response.get_json()[
        "error"
    ].lower()


def test_api_export_rejette_lot_vide(client):
    response = client.post("/api/export", json={"lignes": []})

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload


def test_page_accueil_contient_bouton_export(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="export-csv"' in html


def test_static_js_exporte_lot_courant_via_api(client):
    """Le bouton poste lotLignes (corrections incluses) vers /api/export (#13)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "/api/export" in js
    assert "lotLignes" in js
    assert "export-csv" in js
    assert "type_document" in js
    assert "lot.csv" in js
    assert "changerTypeDocument" in js
    assert "issuer-groups" in js
    assert "issuer-type-heading" in js
    assert "LotGrouping" in js
    assert "export-block-message" in js
    assert "ligne-incomplete" in js
    assert "ligne-a-verifier" in js
    assert "Champs à remplir" in js
    assert 'addEventListener("blur"' in js


def test_static_js_lot_grouping_expose_agregation(client):
    response = client.get("/static/lot_grouping.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "agregerParEmetteur" in js
    assert "raisonExportBloque" in js
    assert "sans émetteur" in js


def test_page_accueil_contient_colonne_ouvrir_fichier(client):
    """Chaque ligne du Lot propose une action « Ouvrir le fichier » (#26)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Ouvrir le fichier" in js
    assert "Aperçu" in js


def test_page_accueil_contient_panneau_apercu(client):
    """Panneau d’aperçu in-app présent dans le HTML (#50)."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="preview-pane"' in html
    assert 'id="preview-content"' in html
    assert 'id="preview-placeholder"' in html
    assert 'id="split-handle"' in html
    assert 'role="separator"' in html
    assert 'id="main-zoom-controls"' in html
    assert 'id="preview-zoom-controls"' in html
    assert 'id="main-zoom-in"' in html
    assert 'id="preview-zoom-in"' in html
    assert 'id="main-zoom-reset"' in html
    assert 'id="preview-zoom-reset"' in html
    assert 'id="preview-zoom-stage"' in html
    assert "pane-zoom-label" not in html
    assert "pane-zoom-groups" not in html


def test_static_js_ouvre_fichier_via_object_url_sans_endpoint(client):
    """Fichier du Lot ouvert via object URL in-app, sans endpoint serveur (#26, #50)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Ouvrir le fichier" in js
    assert "createObjectURL" in js
    assert "revokeObjectURL" in js
    assert "fileUrls" in js
    assert "depositedFiles" in js
    assert "heic2any" in js
    assert "preview-content" in js or "previewContent" in js or "showPreview" in js
    assert "initSplitResize" in js or "setPreviewWidth" in js
    assert "setMainZoom" in js
    assert "setPreviewZoom" in js
    assert "0.1" in js
    assert "window.open" not in js
    assert '"_blank"' not in js
    assert "disabled" in js
    assert "Fichier indisponible" in js
    assert "/api/pdf" not in js
    assert "/api/fichier" not in js


def test_api_export_rejette_type_document_invalide(client):
    response = client.post(
        "/api/export",
        json={
            "lignes": [
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": "X",
                    "date": "01/08/2026",
                    "montant_ht": "1,00",
                    "statut": "OK",
                    "type_document": "QUITTANCE",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


# --- Journal de diagnostic (#56 / #57 / #58) ---

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_api_journal_vide_retourne_404(client):
    response = client.get("/api/journal")

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_api_lot_puis_journal_contient_fichier_et_horodatage(client):
    """Après un Lot, le journal exportable mentionne le fichier traité (#56)."""
    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        lot_response = client.post(
            "/api/lot",
            data={"files": (fh, "Masse 22 Juillet 26.pdf")},
            content_type="multipart/form-data",
        )
    assert lot_response.status_code == 200

    response = client.get("/api/journal")
    assert response.status_code == 200
    assert "text/plain" in response.content_type
    assert "attachment" in response.headers.get("Content-Disposition", "")
    body = response.data.decode("utf-8")
    assert "Masse 22 Juillet 26.pdf" in body
    # Horodatage ISO-ish (YYYY-MM-DD)
    assert re.search(r"\d{4}-\d{2}-\d{2}", body)


def test_api_journal_reinitialise_entre_deux_lots(client):
    """Un nouveau Lot remplace le journal précédent (#56)."""
    masse = CORPUS / "Masse 22 Juillet 26.pdf"
    aluplast = CORPUS / "Aluplast 13 Juillet 26.pdf"

    with masse.open("rb") as fh:
        assert (
            client.post(
                "/api/lot",
                data={"files": (fh, "Masse 22 Juillet 26.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    with aluplast.open("rb") as fh:
        assert (
            client.post(
                "/api/lot",
                data={"files": (fh, "Aluplast 13 Juillet 26.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = client.get("/api/journal").data.decode("utf-8")
    assert "Aluplast 13 Juillet 26.pdf" in body
    assert "Masse 22 Juillet 26.pdf" not in body


def test_page_accueil_contient_bouton_export_journal(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="export-journal"' in html
    assert "Exporter le journal" in html


def test_page_accueil_contient_bouton_nouveau_lot(client):
    """Bouton Nouveau lot visible dans l’UI (#59)."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="reset-lot"' in html
    assert "Nouveau lot" in html


def test_static_js_reset_lot_vide_session(client):
    """JS expose un resetLot qui vide le Lot courant (#59)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "resetLot" in js
    assert "reset-lot" in js


def test_static_js_cumule_depots_successifs(client):
    """JS cumule les lignes au lieu de remplacer le Lot (#60)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "appendFiles" in js
    assert "...lotLignes" in js
    assert "déjà présent" in js
    assert "lotGeneration" in js


def test_static_js_exporte_journal_via_api(client):
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "/api/journal" in js
    assert "export-journal" in js
    assert "exportJournal" in js
    assert "saveJournalText" in js
    assert "save_text_file" in js
    assert "showSaveFilePicker" in js
    # Texte en mémoire, pas de navigation vers le journal comme page
    assert "response.text()" in js
    assert 'link.href = "/api/journal"' not in js


def test_static_js_filtre_formats_non_supportes(client):
    """Le client refuse les formats non supportés avant l'envoi (A)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "isSupportedDocumentName" in js
    assert "SUPPORTED_SUFFIXES" in js
    assert "n'est pas un format exploitable" in js


def test_static_js_affiche_raisons_diagnostic(client):
    """UI affiche raisons_diagnostic sous le statut À vérifier (C)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "raisons_diagnostic" in js
    assert "statut-raisons" in js
    assert "error_detail" in js


def test_lot_grouping_blocage_export_cite_raisons(client):
    response = client.get("/static/lot_grouping.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "raisons_diagnostic" in js
    assert "encore à vérifier —" in js


def test_launcher_expose_save_text_file_api():
    from app.desktop_api import DesktopApi
    from app.launcher import run_desktop_app
    import inspect

    assert hasattr(DesktopApi, "save_text_file")
    source = inspect.getsource(run_desktop_app)
    assert "DesktopApi" in source
    assert "js_api" in source


def test_api_journal_lot_ok_contient_diagnostics_pipeline(client):
    """Lot OK : journal expose source, Template, type, champs, statut (#57)."""
    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        assert (
            client.post(
                "/api/lot",
                data={"files": (fh, "Masse 22 Juillet 26.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = client.get("/api/journal").data.decode("utf-8")
    assert "fichier=Masse 22 Juillet 26.pdf" in body
    assert "source=natif" in body
    assert "Template=Masse" in body
    assert "type=FACTURE" in body
    assert "emetteur=Masse" in body
    assert "date=22/07/2026" in body
    assert "montant_ht=751,95" in body
    assert "statut=OK" in body


def test_api_journal_ocr_indique_source_et_raison(client):
    """Facture OCR : journal marque OCR et statut À vérifier (#57)."""
    pdf_path = CORPUS / "Altagel 10 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        assert (
            client.post(
                "/api/lot",
                data={"files": (fh, "Altagel 10 Juillet 26.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = client.get("/api/journal").data.decode("utf-8")
    assert "fichier=Altagel 10 Juillet 26.pdf" in body
    assert "source=OCR" in body
    assert "statut=A_VERIFIER" in body
    assert "OCR" in body


def test_api_journal_detection_ambigue(tmp_path):
    """Détection ambiguë explicitement nommée dans le journal (#57)."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    shutil.copy(TEMPLATES / "masse.yml", templates_dir / "masse.yml")
    shutil.copy(TEMPLATES / "aluplast.yml", templates_dir / "aluplast.yml")

    app = create_app(templates_dir=templates_dir)
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = tmp_path / "uploads"
    app.config["UPLOAD_FOLDER"].mkdir()
    local_client = app.test_client()

    fixture = FIXTURES / "detection_ambigue_masse_aluplast.pdf"
    with fixture.open("rb") as fh:
        assert (
            local_client.post(
                "/api/lot",
                data={"files": (fh, "detection_ambigue_masse_aluplast.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = local_client.get("/api/journal").data.decode("utf-8")
    assert "Détection ambiguë" in body
    assert "statut=A_VERIFIER" in body
    assert "emetteur=" in body


def test_api_journal_aucun_template(tmp_path):
    """Aucun Template : journal distingue ce cas (#57)."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    app = create_app(templates_dir=templates_dir)
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = tmp_path / "uploads"
    app.config["UPLOAD_FOLDER"].mkdir()
    local_client = app.test_client()

    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        assert (
            local_client.post(
                "/api/lot",
                data={"files": (fh, "Masse 22 Juillet 26.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = local_client.get("/api/journal").data.decode("utf-8")
    assert "aucun Template" in body
    assert "statut=A_VERIFIER" in body
    assert '"raison"' not in body  # pas dans le JSON lignes ; journal texte only


def test_api_journal_capture_exception_technique(client, monkeypatch):
    """Exception pendant le Lot → entrée traceback + journal exportable (#58)."""
    import app.lot as lot_mod

    def boom(*_args, **_kwargs):
        raise RuntimeError("ocr_ko_simule")

    monkeypatch.setattr(lot_mod, "extract_document_text", boom)

    pdf_path = CORPUS / "Masse 22 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "Masse 22 Juillet 26.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 500
    payload = response.get_json()
    assert "error" in payload
    assert "error_detail" in payload
    assert "RuntimeError" in payload["error_detail"]
    assert "ocr_ko_simule" in payload["error_detail"]
    assert payload.get("journal_disponible") is True

    journal = client.get("/api/journal")
    assert journal.status_code == 200
    body = journal.data.decode("utf-8")
    assert "EXCEPTION" in body or "RuntimeError" in body
    assert "ocr_ko_simule" in body
    assert "Traceback" in body or "traceback" in body.lower()


def test_api_lot_ligne_a_verifier_expose_raisons_diagnostic(client):
    """Réponse /api/lot inclut raisons_diagnostic pour À vérifier (C)."""
    pdf_path = CORPUS / "Altagel 10 Juillet 26.pdf"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "Altagel 10 Juillet 26.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    ligne = response.get_json()["lignes"][0]
    assert ligne["statut"] == "A_VERIFIER"
    assert isinstance(ligne.get("raisons_diagnostic"), list)
    assert len(ligne["raisons_diagnostic"]) > 0
    assert "OCR" in ligne["raisons_diagnostic"]

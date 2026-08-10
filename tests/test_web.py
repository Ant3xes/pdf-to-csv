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
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "inconnu.pdf;Saisi à la main;01/08/2026;12,50;OK;FACTURE\n"
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
    """POST /api/export télécharge le CSV détail du Lot, Corrections manuelles incluses (#79)."""
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
    assert 'filename="lot-detail.csv"' in response.headers.get("Content-Disposition", "")
    body = response.data.decode()
    assert body == (
        "\ufeff"
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;751,95;OK;FACTURE\n"
        "inconnu.pdf;Saisi à la main;01/08/2026;12,50;OK;AVOIR\n"
    )
    assert "raison" not in body.lstrip("\ufeff").split("\n")[0]


def test_api_export_detail_meme_emetteur(client):
    """Plusieurs factures du même Émetteur → une ligne CSV chacune (#79)."""
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
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;751,95;OK;FACTURE\n"
        "Masse 15 Juillet 26.pdf;Masse;15/07/2026;203,29;OK;FACTURE\n"
    )


def test_api_export_accepte_a_verifier(client):
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

    assert response.status_code == 200
    body = response.data.decode()
    assert "A_VERIFIER" in body
    assert "inconnu.pdf;Masse;01/08/2026;12,50;A_VERIFIER;FACTURE" in body


def test_api_export_accepte_emetteur_manquant(client):
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

    assert response.status_code == 200
    assert "inconnu.pdf;;01/08/2026;12,50;OK;FACTURE" in response.data.decode()


def test_api_export_facture_et_avoir_detail(client):
    """Facture et Avoir restent des lignes distinctes dans le CSV détail (#79)."""
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
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "Masse 22 Juillet 26.pdf;Hennequin;22/07/2026;1751,30;OK;FACTURE\n"
        "Hennequin AVOIR 10 Juillet 26.pdf;Hennequin;10/07/2026;-1350,50;OK;AVOIR\n"
    )


def test_api_export_accepte_sans_date_ou_montant(client):
    """Export accepte des champs date/montant vides (#79)."""
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

    assert response.status_code == 200
    assert "inconnu.pdf;Masse;;12,50;OK;FACTURE" in response.data.decode()


def test_api_export_rejette_lot_vide(client):
    response = client.post("/api/export", json={"lignes": []})

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload


def test_api_export_agrege_avec_sans_emetteur_en_detail(client):
    """Mode agrege : totaux par Émetteur nommé, détail ligne à ligne sans Émetteur."""
    response = client.post(
        "/api/export",
        json={
            "mode": "agrege",
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
                {
                    "fichier": "inconnu.pdf",
                    "emetteur": None,
                    "date": "01/08/2026",
                    "montant_ht": "12,50",
                    "statut": "A_VERIFIER",
                    "type_document": "FACTURE",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert 'filename="lot-groupe.csv"' in response.headers.get("Content-Disposition", "")
    assert response.data.decode() == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents;fichier;date;statut;type\n"
        ";12,50;1;inconnu.pdf;01/08/2026;A_VERIFIER;FACTURE\n"
        "Masse;955,24;2;;;;\n"
    )


def test_api_export_mode_invalide(client):
    response = client.post(
        "/api/export",
        json={
            "mode": "pdf",
            "lignes": [
                {
                    "fichier": "a.pdf",
                    "emetteur": "Masse",
                    "date": "01/01/2026",
                    "montant_ht": "1,00",
                    "statut": "OK",
                    "type_document": "FACTURE",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "mode" in response.get_json()["error"].lower()


def test_page_accueil_contient_bouton_export(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="export-csv-detail"' in html
    assert 'id="export-csv-agrege"' in html
    assert "Exporter détail" in html
    assert "Exporter groupé" in html


def test_static_js_exporte_lot_courant_via_api(client):
    """Le bouton poste lotLignes (corrections incluses) vers /api/export (#13)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "/api/export" in js
    assert "lotLignes" in js
    assert "export-csv-detail" in js
    assert "export-csv-agrege" in js
    assert "type_document" in js
    assert "lot-detail.csv" in js
    assert "lot-groupe.csv" in js
    assert 'mode: exportMode' in js
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
    assert "messageAvertissementExport" in js
    assert "raisonExportBloque" not in js
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
    """Fichier du Lot ouvert via object URL / pdf.js in-app, sans endpoint serveur (#26, #50, #71)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Ouvrir le fichier" in js
    assert "createObjectURL" in js
    assert "revokeObjectURL" in js
    assert "fileUrls" in js
    assert "depositedFiles" in js
    assert "heic2any" in js
    assert "pdf.min.js" in js
    assert "pdf.worker.min.js" in js
    assert "renderPdfPages" in js or "getDocument" in js
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


def test_static_pdfjs_vendor_servi(client):
    """Assets pdf.js vendored disponibles pour l’aperçu desktop (#71)."""
    for path in ("/static/vendor/pdf.min.js", "/static/vendor/pdf.worker.min.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert len(response.data) > 1000


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
    # Horodatage date + heure locales (Europe/Paris)
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body)
    assert "action=pipeline" in body


def test_api_journal_cumule_deux_lots_sans_clear(client):
    """Deux dépôts successifs s’ajoutent au journal de session (#61)."""
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
    assert "Masse 22 Juillet 26.pdf" in body
    assert "Aluplast 13 Juillet 26.pdf" in body


def test_api_journal_reset_vide_le_journal(client):
    """POST /api/journal/reset vide le journal de session (#61)."""
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
    assert client.get("/api/journal").status_code == 200

    reset = client.post("/api/journal/reset")
    assert reset.status_code == 204

    assert client.get("/api/journal").status_code == 404


def test_page_accueil_contient_bouton_export_journal(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert 'id="export-journal"' in html
    assert "Journal" in html
    # Bouton discret dans la toolbar du panneau gauche, pas dans export-actions
    assert "pane-toolbar-actions" in html
    export_actions = html.split('class="export-actions"', 1)[1].split("</p>", 1)[0]
    assert "export-journal" not in export_actions


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
    assert "saveTextFile" in js
    assert "save_text_file" in js
    assert "showSaveFilePicker" in js
    assert "window.confirm" in js
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


def test_static_js_n_affiche_pas_raisons_sous_statut(client):
    """Les causes de À vérifier ne s'affichent pas dans la colonne statut (journal seulement)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "statut-raisons" not in js
    assert "messageUtilisateurRaisons" not in js
    assert "RAISON_MESSAGES" not in js
    assert "payload.error_detail" not in js


def test_lot_grouping_confirmation_export_a_verifier(client):
    response = client.get("/static/lot_grouping.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "messageAvertissementExport" in js
    assert "pas vérifiées" in js
    assert "aVerifierCount" in js
    assert "Export impossible" not in js


def test_launcher_expose_save_text_file_api():
    from app.desktop_api import DesktopApi
    from app.launcher import run_desktop_app
    import inspect

    assert hasattr(DesktopApi, "save_text_file")
    source = inspect.getsource(DesktopApi.save_text_file)
    assert "FileDialog" in source
    assert "SAVE" in source
    launcher_source = inspect.getsource(run_desktop_app)
    assert "DesktopApi" in launcher_source
    assert "js_api" in launcher_source


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
    """Vrai OCR (pas de texte natif) : journal marque OCR et statut À vérifier (#57)."""
    pdf_path = FIXTURES / "scan_sans_texte.pdf"
    with pdf_path.open("rb") as fh:
        assert (
            client.post(
                "/api/lot",
                data={"files": (fh, "scan_sans_texte.pdf")},
                content_type="multipart/form-data",
            ).status_code
            == 200
        )

    body = client.get("/api/journal").data.decode("utf-8")
    assert "fichier=scan_sans_texte.pdf" in body
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
    pdf_path = FIXTURES / "scan_sans_texte.pdf"
    with pdf_path.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, "scan_sans_texte.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    ligne = response.get_json()["lignes"][0]
    assert ligne["statut"] == "A_VERIFIER"
    assert isinstance(ligne.get("raisons_diagnostic"), list)
    assert len(ligne["raisons_diagnostic"]) > 0
    assert "OCR" in ligne["raisons_diagnostic"]


# --- Journal de session / actions utilisateur (#61) ---


def test_api_journal_events_enregistre_actions_metier(client):
    """POST /api/journal/events append chaque action métier au journal (#61)."""
    events = [
        {"action": "depot", "resultat": "accepte", "fichier": "a.pdf"},
        {"action": "depot", "resultat": "refuse", "fichier": "x.exe"},
        {"action": "depot", "resultat": "doublon", "fichier": "a.pdf"},
        {
            "action": "correction",
            "fichier": "a.pdf",
            "champ": "montant_ht",
            "valeur": "12,00",
        },
        {"action": "validation", "fichier": "a.pdf"},
        {"action": "type_document", "fichier": "a.pdf", "type": "AVOIR"},
        {"action": "apercu", "fichier": "a.pdf"},
        {
            "action": "export_csv",
            "mode": "detail",
            "confirm": "confirmed",
            "save": "ok",
        },
        {
            "action": "export_csv",
            "mode": "agrege",
            "confirm": "cancelled",
        },
        {"action": "export_journal", "save": "cancelled"},
        {"action": "nouveau_lot"},
    ]
    response = client.post("/api/journal/events", json={"events": events})
    assert response.status_code == 204

    body = client.get("/api/journal").data.decode("utf-8")
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} action=depot", body)
    assert "resultat=accepte" in body
    assert "fichier=a.pdf" in body
    assert "resultat=refuse" in body
    assert "action=correction" in body
    assert "champ=montant_ht" in body
    assert "valeur=12,00" in body
    assert "action=validation" in body
    assert "action=type_document" in body
    assert "type=AVOIR" in body
    assert "action=apercu" in body
    assert "action=export_csv" in body
    assert "mode=detail" in body
    assert "confirm=confirmed" in body
    assert "save=ok" in body
    assert "mode=agrege" in body
    assert "confirm=cancelled" in body
    assert "action=export_journal" in body
    assert "action=nouveau_lot" in body


def test_api_journal_events_action_inconnue_retourne_400(client):
    """Action inconnue → 400, journal inchangé (#61)."""
    client.post(
        "/api/journal/events",
        json={"events": [{"action": "validation", "fichier": "ok.pdf"}]},
    )
    before = client.get("/api/journal").data.decode("utf-8")

    response = client.post(
        "/api/journal/events",
        json={"events": [{"action": "zoom", "level": "2"}]},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()

    after = client.get("/api/journal").data.decode("utf-8")
    assert after == before
    assert "action=zoom" not in after


def test_api_journal_events_payload_invalide_retourne_400(client):
    response = client.post("/api/journal/events", json={"events": "nope"})
    assert response.status_code == 400

    response = client.post("/api/journal/events", json={})
    assert response.status_code == 400


def test_static_js_journalise_actions_utilisateur(client):
    """Le front envoie les actions métier au journal de session (#61)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "journaliserAction" in js
    assert "/api/journal/events" in js
    assert "/api/journal/reset" in js
    assert 'action: "depot"' in js or 'action:"depot"' in js
    assert 'action: "correction"' in js or 'action:"correction"' in js
    assert 'action: "validation"' in js or 'action:"validation"' in js
    assert 'action: "type_document"' in js or 'action:"type_document"' in js
    assert 'action: "apercu"' in js or 'action:"apercu"' in js
    assert 'action: "export_csv"' in js or 'action:"export_csv"' in js
    assert 'action: "export_journal"' in js or 'action:"export_journal"' in js
    assert 'resultat: "accepte"' in js or 'resultat:"accepte"' in js
    # Nouveau lot : clear seul (action nouveau_lot optionnelle côté API)
    # Pas de journalisation du bruit UI
    assert 'action: "zoom"' not in js
    assert 'action:"zoom"' not in js

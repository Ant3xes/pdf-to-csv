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
    assert 'id="factures-table"' in html
    assert 'id="avoirs-table"' in html
    assert 'id="avoirs-section"' in html
    assert 'id="totaux-emetteurs"' in html
    assert 'id="export-block-message"' in html
    assert "Factures" in html
    assert "Avoirs" in html
    assert "Totaux par émetteur" in html
    assert "Type" in html
    assert "fichier" in html.lower()
    assert "émetteur" in html.lower() or "emetteur" in html.lower()
    assert "montant" in html.lower()
    assert "statut" in html.lower()
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
    """Colonne d'action pour Valider une Facture À vérifier (#27)."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert "<th>Action</th>" in html or "Valider" in html


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
        "emetteur;montant_ht;nb_documents\n"
        "Masse;751,95;1\n"
        "Saisi à la main;12,50;1\n"
    )
    assert "raison" not in body.split("\n")[0]


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
        "emetteur;montant_ht;nb_documents\n"
        "Hennequin;400,80;2\n"
    )


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
    assert "factures-table" in js
    assert "avoirs-table" in js
    assert "LotGrouping" in js
    assert "groupe-emetteur" in js
    assert "export-block-message" in js


def test_static_js_lot_grouping_expose_agregation(client):
    response = client.get("/static/lot_grouping.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "agregerParEmetteur" in js
    assert "raisonExportBloque" in js
    assert "sans émetteur" in js


def test_page_accueil_contient_colonne_ouvrir_fichier(client):
    """Chaque ligne du Lot propose une action « Ouvrir le fichier » (#26)."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.data.decode()
    assert "<th>Aperçu</th>" in html


def test_static_js_ouvre_fichier_via_object_url_sans_endpoint(client):
    """Fichier du Lot ouvert via object URL navigateur, sans endpoint serveur (#26)."""
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "Ouvrir le fichier" in js
    assert "createObjectURL" in js
    assert "revokeObjectURL" in js
    assert "fileUrls" in js
    assert "depositedFiles" in js
    assert "heic2any" in js
    assert '"_blank"' in js
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

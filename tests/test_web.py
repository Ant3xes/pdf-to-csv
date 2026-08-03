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
    assert 'id="results-table"' in html
    assert "fichier" in html.lower()
    assert "émetteur" in html.lower() or "emetteur" in html.lower()
    assert "montant" in html.lower()
    assert "statut" in html.lower()
    assert "app.js" in html


def test_static_js_gere_depot_et_tableau(client):
    response = client.get("/static/app.js")

    assert response.status_code == 200
    js = response.data.decode()
    assert "dragover" in js
    assert "/api/lot" in js
    assert "processing-indicator" in js
    assert "À vérifier" in js


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
    assert ligne["montant_ttc"] == "793,31"
    assert ligne["statut"] == "OK"


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
    assert set(lignes[1]) >= {"fichier", "emetteur", "date", "montant_ttc", "statut"}


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


def test_api_lot_rejette_non_pdf_avec_message_clair(client):
    non_pdf = CORPUS / "Quittance [locataire] Juillet 26.heic"
    with non_pdf.open("rb") as fh:
        response = client.post(
            "/api/lot",
            data={"files": (fh, non_pdf.name)},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
    assert "pdf" in payload["error"].lower()
    assert non_pdf.name in payload["error"]
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

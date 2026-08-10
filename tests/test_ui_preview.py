import re
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
BLOB_SRC = re.compile(r"^blob:")
PREVIEW_MEDIA = (
    "#preview-content .preview-pdf, "
    "#preview-content iframe, "
    "#preview-content embed, "
    "#preview-content img"
)
PREVIEW_PDF_CANVAS = "#preview-content .preview-pdf canvas"


def test_apercu_pdf_dans_panneau_droit(live_server_url, page: Page):
    """Dépôt PDF → Ouvrir le fichier → aperçu canvas pdf.js (#50, #71)."""
    page.goto(live_server_url)
    expect(page.locator("#preview-pane")).to_be_visible()
    expect(page.locator("#preview-placeholder")).to_be_visible()

    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    page.click(".ouvrir-fichier")

    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()
    expect(page.locator("#preview-filename")).to_have_text("Masse 22 Juillet 26.pdf")
    expect(page.locator("tr.ligne-apercu")).to_have_count(1)
    expect(page.locator("#preview-placeholder")).to_be_hidden()


def test_apercu_image_dans_panneau_droit(live_server_url, page: Page):
    """Dépôt image → Ouvrir le fichier → aperçu image in-app (#50)."""
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    page.click(".ouvrir-fichier")

    expect(page.locator("#preview-content img")).to_be_visible()
    expect(page.locator("#preview-content img")).to_have_attribute("src", BLOB_SRC)
    expect(page.locator("tr.ligne-apercu")).to_have_count(1)


def test_apercu_change_de_ligne(live_server_url, page: Page):
    """Changement de ligne met à jour l’aperçu (#50)."""
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            FIXTURES / "scan_sans_texte.png",
        ],
    )
    page.wait_for_selector(".issuer-group")
    expect(page.locator(".ouvrir-fichier:not([disabled])")).to_have_count(2)

    page.locator("tr", has_text="Masse 22 Juillet 26.pdf").locator(
        ".ouvrir-fichier"
    ).click()
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()
    expect(page.locator("#preview-filename")).to_have_text("Masse 22 Juillet 26.pdf")

    page.locator("tr", has_text="scan_sans_texte.png").locator(".ouvrir-fichier").click()
    second = page.locator("#preview-content img")
    expect(second).to_be_visible()
    expect(second).to_have_attribute("src", BLOB_SRC)
    expect(page.locator("#preview-filename")).to_have_text("scan_sans_texte.png")


def test_apercu_pdf_retour_premiere_ligne(live_server_url, page: Page):
    """Retour sur un PDF déjà ouvert régénère l’aperçu canvas (#71)."""
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            CORPUS / "Masse 23 Juillet 26.pdf",
        ],
    )
    page.wait_for_selector(".issuer-group")
    boutons = page.locator(".ouvrir-fichier:not([disabled])")
    expect(boutons).to_have_count(2)

    boutons.nth(0).click()
    expect(page.locator("#preview-filename")).to_have_text("Masse 22 Juillet 26.pdf")
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()

    boutons.nth(1).click()
    expect(page.locator("#preview-filename")).to_have_text("Masse 23 Juillet 26.pdf")
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()

    boutons.nth(0).click()
    expect(page.locator("#preview-filename")).to_have_text("Masse 22 Juillet 26.pdf")
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()
    expect(page.locator("#preview-placeholder")).to_be_hidden()
    expect(page.locator("tr.ligne-apercu")).to_have_count(1)


def test_bouton_nouveau_lot_vide_la_session(live_server_url, page: Page):
    """Bouton Nouveau lot vide documents, aperçu et exports (#59)."""
    page.goto(live_server_url)
    expect(page.locator("#reset-lot")).to_be_visible()
    expect(page.locator("#reset-lot")).to_have_text("Nouveau lot")

    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            FIXTURES / "scan_sans_texte.png",
        ],
    )
    page.wait_for_selector(".issuer-group")
    page.click(".ouvrir-fichier:not([disabled])")
    expect(page.locator(PREVIEW_MEDIA)).to_be_visible()
    expect(page.locator("#export-journal")).to_be_enabled()

    page.click("#reset-lot")

    expect(page.locator("#factures-count")).to_have_text("0")
    expect(page.locator("#avoirs-count")).to_have_text("0")
    expect(page.locator(".issuer-group")).to_have_count(0)
    expect(page.locator("#totaux-emetteurs")).to_be_hidden()
    expect(page.locator("#preview-placeholder")).to_be_visible()
    expect(page.locator(PREVIEW_MEDIA)).to_have_count(0)
    expect(page.locator("tr.ligne-apercu")).to_have_count(0)
    expect(page.locator("#export-csv-detail")).to_be_disabled()
    expect(page.locator("#export-journal")).to_be_disabled()


def test_depot_successif_cumule_les_factures(live_server_url, page: Page):
    """Un second dépôt ajoute au Lot sans remplacer le premier (#60)."""
    page.goto(live_server_url)
    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    expect(page.locator("#factures-count")).to_have_text("1")

    page.click(".ouvrir-fichier:not([disabled])")
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()
    expect(page.locator("#preview-filename")).to_have_text("Masse 22 Juillet 26.pdf")

    page.set_input_files("#file-input", [CORPUS / "Masse 23 Juillet 26.pdf"])
    page.wait_for_function(
        "() => document.getElementById('factures-count')?.textContent === '2'"
    )

    expect(page.locator("#factures-count")).to_have_text("2")
    expect(page.locator(".ouvrir-fichier:not([disabled])")).to_have_count(2)
    expect(page.locator(PREVIEW_PDF_CANVAS).first).to_be_visible()
    expect(page.locator("#preview-placeholder")).to_be_hidden()
    expect(page.locator("tr.ligne-apercu")).to_have_count(1)

    page.click("#reset-lot")
    expect(page.locator("#factures-count")).to_have_text("0")
    expect(page.locator("#preview-placeholder")).to_be_visible()


def test_correction_manuelle_survit_au_depot_suivant(live_server_url, page: Page):
    """Correction manuelle du premier batch intacte après cumul (#60)."""
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector(".issuer-group")

    emetteur = page.get_by_role("textbox", name="Émetteur")
    emetteur.fill("Émetteur corrigé")
    emetteur.blur()
    expect(emetteur).to_have_value("Émetteur corrigé")

    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_function(
        "() => document.querySelectorAll('.ouvrir-fichier:not([disabled])').length === 2"
    )

    expect(page.get_by_role("textbox", name="Émetteur").first).to_have_value(
        "Émetteur corrigé"
    )


def test_doublon_nom_fichier_ignore_avec_avertissement(live_server_url, page: Page):
    """Fichier déjà présent dans le Lot : ignoré + avertissement (#60)."""
    page.goto(live_server_url)
    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    expect(page.locator("#factures-count")).to_have_text("1")

    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    expect(page.locator("#error-message")).to_be_visible()
    expect(page.locator("#error-message")).to_contain_text("Masse 22 Juillet 26.pdf")
    expect(page.locator("#factures-count")).to_have_text("1")
    expect(page.locator(".ouvrir-fichier:not([disabled])")).to_have_count(1)


def test_split_handle_redimensionne_panneau_apercu(live_server_url, page: Page):
    """Glisser le séparateur change la largeur de l’aperçu."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(live_server_url)
    handle = page.locator("#split-handle")
    expect(handle).to_be_visible()

    preview = page.locator("#preview-pane")
    before = preview.bounding_box()["width"]
    box = handle.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 80)
    page.mouse.down()
    page.mouse.move(box["x"] - 140, box["y"] + 80, steps=8)
    page.mouse.up()

    after = preview.bounding_box()["width"]
    assert after > before + 80


def test_zooms_panneaux_independants_par_pas_de_10(live_server_url, page: Page):
    """Zoom tableau et aperçu indépendants ; aperçu agrandit vraiment le média (#77)."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    page.click(".ouvrir-fichier")
    img = page.locator("#preview-content img")
    expect(img).to_be_visible()
    expect(page.locator("#preview-filename")).to_be_visible()

    expect(page.locator("#main-zoom-reset")).to_have_text("100%")
    expect(page.locator("#preview-zoom-reset")).to_have_text("100%")
    media_width_100 = img.bounding_box()["width"]
    filename_width_100 = page.locator("#preview-filename").bounding_box()["width"]

    page.click("#main-zoom-in")
    expect(page.locator("#main-zoom-reset")).to_have_text("110%")
    expect(page.locator("#preview-zoom-reset")).to_have_text("100%")
    expect(page.locator("#main-zoom-stage")).to_have_css(
        "transform",
        re.compile(r"matrix\(1\.1"),
    )
    assert img.bounding_box()["width"] == pytest.approx(media_width_100, rel=0.02)

    page.click("#preview-zoom-in")
    page.click("#preview-zoom-in")
    expect(page.locator("#preview-zoom-reset")).to_have_text("120%")
    expect(page.locator("#main-zoom-reset")).to_have_text("110%")
    media_width_120 = img.bounding_box()["width"]
    content_width_120 = page.locator("#preview-content").bounding_box()["width"]
    assert media_width_120 == pytest.approx(media_width_100 * 1.2, rel=0.05)
    # Régression : le conteneur ne doit pas grossir sans le média (scrollbar seule).
    assert media_width_120 == pytest.approx(content_width_120, rel=0.05)
    assert page.locator("#preview-filename").bounding_box()["width"] == pytest.approx(
        filename_width_100, rel=0.05
    )
    expect(page.locator("#preview-filename")).to_have_css("transform", "none")
    expect(page.locator("#preview-placeholder")).to_have_css("transform", "none")

    page.click("#main-zoom-reset")
    expect(page.locator("#main-zoom-reset")).to_have_text("100%")
    expect(page.locator("#preview-zoom-reset")).to_have_text("120%")

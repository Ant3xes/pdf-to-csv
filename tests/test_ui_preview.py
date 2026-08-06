import re
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
BLOB_SRC = re.compile(r"^blob:")


def test_apercu_pdf_dans_panneau_droit(live_server_url, page: Page):
    """Dépôt PDF → Ouvrir le fichier → aperçu in-app (#50)."""
    page.goto(live_server_url)
    expect(page.locator("#preview-pane")).to_be_visible()
    expect(page.locator("#preview-placeholder")).to_be_visible()

    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    page.click(".ouvrir-fichier")

    expect(page.locator("#preview-content iframe")).to_be_visible()
    expect(page.locator("#preview-content iframe")).to_have_attribute("src", BLOB_SRC)
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


def test_apercu_change_de_ligne_et_reset_nouveau_lot(live_server_url, page: Page):
    """Changement de ligne met à jour l’aperçu ; nouveau Lot le réinitialise (#50)."""
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            FIXTURES / "scan_sans_texte.png",
        ],
    )
    page.wait_for_selector(".issuer-group")
    boutons = page.locator(".ouvrir-fichier:not([disabled])")
    expect(boutons).to_have_count(2)

    boutons.nth(0).click()
    first_src = page.locator("#preview-content iframe, #preview-content img").get_attribute(
        "src"
    )
    assert first_src and first_src.startswith("blob:")

    boutons.nth(1).click()
    second = page.locator("#preview-content iframe, #preview-content img")
    expect(second).to_be_visible()
    second_src = second.get_attribute("src")
    assert second_src and second_src.startswith("blob:")
    assert second_src != first_src

    page.set_input_files("#file-input", [CORPUS / "Masse 23 Juillet 26.pdf"])
    page.wait_for_selector(".ouvrir-fichier:not([disabled])")
    expect(page.locator("#preview-placeholder")).to_be_visible()
    expect(page.locator("#preview-content iframe, #preview-content img")).to_have_count(0)
    expect(page.locator("tr.ligne-apercu")).to_have_count(0)

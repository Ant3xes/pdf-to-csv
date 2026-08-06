from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "accept_downloads": True}


def test_totaux_et_groupes_apres_depot_masse(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            CORPUS / "Masse 23 Juillet 26.pdf",
            CORPUS / "Masse 28 Juillet 26.pdf",
        ],
    )
    page.wait_for_selector("#totaux-emetteurs:not([hidden])")

    expect(page.locator("#totaux-emetteurs-list .totaux-emetteur-card")).to_have_count(1)
    expect(page.locator(".totaux-emetteur-nom")).to_contain_text("Masse")
    expect(page.locator(".totaux-emetteur-montant")).to_contain_text("1 578,39")
    expect(page.locator(".totaux-emetteur-meta")).to_contain_text("3 documents")
    expect(page.locator(".issuer-group")).to_have_count(1)
    expect(page.locator(".issuer-group-title")).to_contain_text("Masse")
    expect(page.locator(".issuer-type-heading")).to_contain_text("Factures (3)")
    expect(page.locator("#export-csv")).to_be_enabled()


def test_export_bloque_si_a_verifier(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector(".issuer-group")

    expect(page.locator("#export-csv")).to_be_disabled()
    expect(page.locator("#export-block-message")).to_be_visible()
    expect(page.locator("#export-block-message")).to_contain_text("à vérifier")
    expect(page.locator(".issuer-group tr.ligne-a-verifier")).to_have_count(1)


def test_export_reussi_apres_validation_ligne(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector("#export-csv[disabled]")
    expect(page.locator("#export-block-message")).to_contain_text("à vérifier")

    page.click(".valider-ligne")
    expect(page.locator("#export-csv")).to_be_enabled()
    expect(page.locator("#export-block-message")).to_be_hidden()

    with page.expect_download() as download_info:
        page.click("#export-csv")
    content = download_info.value.path().read_text(encoding="utf-8")
    assert content == "emetteur;montant_ht;nb_documents\nAltagel;99,50;1\n"


def test_ligne_incomplete_et_box_indiquent_les_champs_manquants(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "champ_manquant_montant.png"])
    page.wait_for_selector(".issuer-group")

    expect(page.locator(".issuer-group tr.ligne-incomplete")).to_have_count(1)
    expect(page.locator(".totaux-emetteur-card.incomplet")).to_have_count(1)
    expect(page.locator(".totaux-emetteur-warning-title")).to_contain_text("Champs à remplir")
    expect(page.locator(".totaux-emetteur-warning-list")).to_contain_text("Montant HT")


def test_sans_emetteur_est_premier_et_en_rouge(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            CORPUS / "Masse 23 Juillet 26.pdf",
        ],
    )
    page.wait_for_selector(".issuer-group")
    emetteur_input = page.locator('input[aria-label="Émetteur"]').first
    emetteur_input.fill("")
    emetteur_input.press("Tab")

    expect(page.locator(".issuer-group")).to_have_count(2)
    expect(page.locator(".issuer-group-title").first).to_contain_text("sans émetteur")
    expect(page.locator(".issuer-group").first).to_have_class("issuer-group issuer-group-missing")


def test_un_emetteur_affiche_factures_et_avoirs_separes(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files(
        "#file-input",
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            CORPUS / "Hennequin AVOIR 10 Juillet 26.pdf",
        ],
    )
    page.wait_for_selector(".issuer-group")

    expect(page.locator(".issuer-group")).to_have_count(2)
    expect(page.locator(".issuer-group-title")).to_contain_text(["Hennequin", "Masse"])
    expect(page.locator(".issuer-group").filter(has_text="Hennequin").locator(".issuer-type-heading")).to_contain_text("Avoirs (1)")
    expect(page.locator(".issuer-group").filter(has_text="Masse").locator(".issuer-type-heading")).to_contain_text("Factures (1)")


def test_export_reussi_apres_lot_ok(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector("#export-csv:not([disabled])")

    with page.expect_download() as download_info:
        page.click("#export-csv")
    download = download_info.value
    content = download.path().read_text(encoding="utf-8")
    assert content == "emetteur;montant_ht;nb_documents\nMasse;751,95;1\n"

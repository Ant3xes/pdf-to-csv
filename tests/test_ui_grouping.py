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

    expect(page.locator("#totaux-emetteurs-list .totaux-emetteur")).to_have_count(1)
    expect(page.locator("#totaux-emetteurs-list .totaux-emetteur")).to_contain_text(
        "Masse — total net HT : 1578,39 (3 doc.)"
    )
    expect(page.locator("#factures-table tr.groupe-emetteur")).to_have_count(1)
    expect(page.locator("#export-csv")).to_be_enabled()


def test_export_bloque_si_a_verifier(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [FIXTURES / "scan_sans_texte.png"])
    page.wait_for_selector("#factures-table tr.groupe-emetteur")

    expect(page.locator("#export-csv")).to_be_disabled()
    expect(page.locator("#export-block-message")).to_be_visible()
    expect(page.locator("#export-block-message")).to_contain_text("à vérifier")


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


def test_export_reussi_apres_lot_ok(live_server_url, page: Page):
    page.goto(live_server_url)
    page.set_input_files("#file-input", [CORPUS / "Masse 22 Juillet 26.pdf"])
    page.wait_for_selector("#export-csv:not([disabled])")

    with page.expect_download() as download_info:
        page.click("#export-csv")
    download = download_info.value
    content = download.path().read_text(encoding="utf-8")
    assert content == "emetteur;montant_ht;nb_documents\nMasse;751,95;1\n"

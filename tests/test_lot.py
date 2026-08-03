from pathlib import Path

from app.lot import process_lot

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"


def test_lot_masse_extrait_emetteur_date_montant_ok():
    lignes = process_lot(
        [CORPUS / "Masse 22 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Masse 22 Juillet 26.pdf"
    assert ligne.emetteur == "Masse"
    assert ligne.date == "22/07/2026"
    assert ligne.montant_ttc == "793,31"
    assert ligne.statut == "OK"


def test_lot_domaine_des_jumeaux_net_a_payer_ok():
    lignes = process_lot(
        [CORPUS / "Domaine des jumeaux 4 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Domaine des jumeaux 4 Juillet 26.pdf"
    assert ligne.emetteur == "Domaine des Jumeaux"
    assert ligne.date == "04/07/2026"
    assert ligne.montant_ttc == "419,04"
    assert ligne.statut == "OK"


def test_lot_devaud_une_seule_ligne_malgre_multi_pages_et_bl():
    lignes = process_lot(
        [CORPUS / "devaud 20 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "devaud 20 Juillet 26.pdf"
    assert ligne.emetteur == "Devaud"
    assert ligne.date == "20/07/2026"
    assert ligne.montant_ttc == "615,68"
    assert ligne.statut == "OK"


def test_lot_aluplast_montant_ttc_pas_ht_ni_tva():
    lignes = process_lot(
        [CORPUS / "Aluplast 13 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Aluplast 13 Juillet 26.pdf"
    assert ligne.emetteur == "Aluplast"
    assert ligne.date == "13/07/2026"
    assert ligne.montant_ttc == "323,40"
    assert ligne.statut == "OK"


def test_lot_plusieurs_pdf_meme_fournisseur_restent_lignes_distinctes():
    lignes = process_lot(
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            CORPUS / "Masse 23 Juillet 26.pdf",
            CORPUS / "Masse 28 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 3
    assert [l.fichier for l in lignes] == [
        "Masse 22 Juillet 26.pdf",
        "Masse 23 Juillet 26.pdf",
        "Masse 28 Juillet 26.pdf",
    ]
    assert [l.emetteur for l in lignes] == ["Masse", "Masse", "Masse"]
    assert [l.date for l in lignes] == ["22/07/2026", "23/07/2026", "28/07/2026"]
    assert [l.montant_ttc for l in lignes] == ["793,31", "214,47", "657,42"]
    assert all(l.statut == "OK" for l in lignes)

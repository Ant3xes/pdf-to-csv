import shutil
from pathlib import Path

from app.csv_export import export_csv
from app.lot import corriger_ligne, process_lot

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def test_lot_hennequin_facture_et_avoir_meme_template():
    lignes = process_lot(
        [
            CORPUS / "Hennequin 20 Juillet 26.pdf",
            CORPUS / "Hennequin AVOIR 10 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 2
    facture, avoir = lignes
    assert facture.fichier == "Hennequin 20 Juillet 26.pdf"
    assert facture.emetteur == "Hennequin"
    assert facture.date == "20/07/2026"
    assert facture.montant_ttc == "1 847,62".replace(" ", "")
    assert facture.statut == "OK"
    assert avoir.fichier == "Hennequin AVOIR 10 Juillet 26.pdf"
    assert avoir.emetteur == "Hennequin"
    assert avoir.date == "10/07/2026"
    assert avoir.montant_ttc == "-1 424,78".replace(" ", "")
    assert avoir.statut == "OK"


def test_lot_veolia_avoir_extrait_credit_et_date():
    lignes = process_lot(
        [CORPUS / "Véolia eaux Avoir 22 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Véolia eaux Avoir 22 Juillet 26.pdf"
    assert ligne.emetteur == "Veolia Eau"
    assert ligne.date == "22/07/2026"
    assert ligne.montant_ttc == "-1240,63"
    assert ligne.statut == "OK"


def test_lot_vives_eaux_factures_et_avoir_meme_template():
    lignes = process_lot(
        [
            CORPUS / "Vives eaux 10 Juillet 26.pdf",
            CORPUS / "Vives eaux 20 Juillet 26.pdf",
            CORPUS / "Vives eaux Avoir 20 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 3
    assert [ligne.fichier for ligne in lignes] == [
        "Vives eaux 10 Juillet 26.pdf",
        "Vives eaux 20 Juillet 26.pdf",
        "Vives eaux Avoir 20 Juillet 26.pdf",
    ]
    assert all(ligne.emetteur == "Vives Eaux" for ligne in lignes)
    assert [ligne.date for ligne in lignes] == ["10/07/2026", "20/07/2026", "20/07/2026"]
    assert [ligne.montant_ttc for ligne in lignes] == ["2604,65", "3775,26", "-39,00"]
    assert all(ligne.statut == "OK" for ligne in lignes)


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


def test_lot_facture_sans_template_filet_date_montant_a_verifier(tmp_path):
    """Sans Template : filet générique préremplit date/montant, pas d'Émetteur (#29)."""
    lignes = process_lot(
        [CORPUS / "ACR 1 Juillet 26.pdf"],
        tmp_path,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "ACR 1 Juillet 26.pdf"
    assert ligne.emetteur is None
    assert ligne.date == "01/07/2026"
    assert ligne.montant_ttc == "144,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_generique_corpus_sans_template(tmp_path):
    """Smoke Corpus sans YAML : Compagnie, SPRE, Youtrust via filet (#29)."""
    compagnie = next(CORPUS.glob("Compagnie*Juillet*.pdf"))
    lignes = process_lot(
        [
            compagnie,
            CORPUS / "SPRE 1er Juillet 26.pdf",
            CORPUS / "Youtrust 19 Juillet 26.pdf",
        ],
        tmp_path,
    )

    assert [l.emetteur for l in lignes] == [None, None, None]
    assert all(l.statut == "A_VERIFIER" for l in lignes)
    assert lignes[0].date == "20/07/2026"
    assert lignes[0].montant_ttc == "272,72"
    assert lignes[1].date == "01/07/2026"
    assert lignes[1].montant_ttc == "629,71"
    assert lignes[2].date == "19/07/2026"
    assert lignes[2].montant_ttc == "13,20"


def test_lot_filet_rien_extractible_champs_vides_a_verifier():
    """Texte sans indices fiables → champs vides + A_VERIFIER (#29)."""
    lignes = process_lot(
        [FIXTURES / "rien_extractible.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur is None
    assert ligne.date is None
    assert ligne.montant_ttc is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_detection_ambigue_filet_sans_emetteur(tmp_path):
    """≥2 templates matchent → aucun appliqué ; filet peut préremplir (#30)."""
    shutil.copy(TEMPLATES / "masse.yml", tmp_path / "masse.yml")
    shutil.copy(TEMPLATES / "aluplast.yml", tmp_path / "aluplast.yml")

    lignes = process_lot(
        [FIXTURES / "detection_ambigue_masse_aluplast.pdf"],
        tmp_path,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "detection_ambigue_masse_aluplast.pdf"
    assert ligne.emetteur is None
    assert ligne.date == "12/03/2026"
    assert ligne.montant_ttc == "55,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_dates_ambigues_date_vide():
    """Plusieurs dates libellées sans vainqueur → date vide (#30)."""
    lignes = process_lot(
        [FIXTURES / "filet_dates_ambigues.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur is None
    assert ligne.date is None
    assert ligne.montant_ttc == "100,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_ht_vs_ttc_ne_prend_pas_ht():
    """Concurrence HT vs TTC → le HT n'est pas retenu (#30)."""
    lignes = process_lot(
        [FIXTURES / "filet_ht_vs_ttc.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.montant_ttc == "100,00"
    assert ligne.montant_ttc != "80,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_montants_ttc_ambigus_montant_vide():
    """Plusieurs montants TTC/Net à payer distincts → montant vide (#30)."""
    lignes = process_lot(
        [FIXTURES / "filet_montants_ambigus.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.date == "01/07/2026"
    assert ligne.montant_ttc is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_acr_template_ok():
    lignes = process_lot([CORPUS / "ACR 1 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "ACR"
    assert ligne.date == "01/07/2026"
    assert ligne.montant_ttc == "144,00"
    assert ligne.statut == "OK"


def test_lot_spre_template_ok():
    lignes = process_lot([CORPUS / "SPRE 1er Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "SPRE"
    assert ligne.date == "01/07/2026"
    assert ligne.montant_ttc == "629,71"
    assert ligne.statut == "OK"


def test_lot_youtrust_template_ok():
    lignes = process_lot([CORPUS / "Youtrust 19 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Youtrust"
    assert ligne.date == "19/07/2026"
    assert ligne.montant_ttc == "13,20"
    assert ligne.statut == "OK"


def test_lot_compagnie_deboucheurs_template_ok():
    compagnie = next(CORPUS.glob("Compagnie*Juillet*.pdf"))
    lignes = process_lot([compagnie], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Compagnie des Déboucheurs"
    assert ligne.date == "20/07/2026"
    assert ligne.montant_ttc == "272,72"
    assert ligne.statut == "OK"


def test_lot_domaine_verzier_template_ok():
    lignes = process_lot([CORPUS / "Domaine Verzier 29 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Domaine Verzier"
    assert ligne.date == "29/07/2026"
    assert ligne.montant_ttc == "1147,92"
    assert ligne.statut == "OK"


def test_lot_valrhona_deux_pdf_meme_template_ok():
    lignes = process_lot(
        [
            CORPUS / "Valrhona 1er Juillet 26.pdf",
            CORPUS / "Valrhona 20 Juillet 26.pdf",
        ],
        TEMPLATES,
    )
    assert len(lignes) == 2
    assert all(l.emetteur == "Valrhona" for l in lignes)
    assert [l.date for l in lignes] == ["01/07/2026", "20/07/2026"]
    assert [l.montant_ttc for l in lignes] == ["197,05", "197,05"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_anse_du_piquet_deux_pdf_meme_template_ok():
    lignes = process_lot(
        [
            CORPUS / "L'Anse du Piquet 10 Juillet 26.pdf",
            CORPUS / "L'Anse du Piquet 20 Juillet 26.pdf",
        ],
        TEMPLATES,
    )
    assert len(lignes) == 2
    assert all(l.emetteur == "L'Anse du Piquet" for l in lignes)
    assert [l.date for l in lignes] == ["10/07/2026", "20/07/2026"]
    assert [l.montant_ttc for l in lignes] == ["175,55", "438,88"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_metro_deux_pdf_meme_template_ok():
    metro_paths = sorted(CORPUS.glob("M*tro*Juillet*.pdf"))
    assert len(metro_paths) == 2
    lignes = process_lot(metro_paths, TEMPLATES)
    assert len(lignes) == 2
    assert all(l.emetteur == "Métro" for l in lignes)
    assert [l.date for l in lignes] == ["01/07/2026", "08/07/2026"]
    assert [l.montant_ttc for l in lignes] == ["1985,73", "2396,06"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_hotel_formule1_ocr_champs_mais_a_verifier():
    formule = next(CORPUS.glob("Hotel Formule*"))
    lignes = process_lot([formule], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == formule.name
    assert ligne.emetteur == "Hotel Formule 1"
    assert ligne.date == "05/07/2026"
    assert ligne.montant_ttc == "34,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_altagel_scan_ocr_extrait_champs_mais_a_verifier():
    lignes = process_lot(
        [CORPUS / "Altagel 10 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Altagel 10 Juillet 26.pdf"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "10/07/2026"
    assert ligne.montant_ttc == "382,26"
    assert ligne.statut == "A_VERIFIER"


def test_lot_pdf_sans_texte_natif_bascule_ocr_avant_extraction():
    lignes = process_lot(
        [FIXTURES / "scan_sans_texte.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "scan_sans_texte.pdf"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "15/03/2026"
    assert ligne.montant_ttc == "99,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_champ_obligatoire_manquant_a_verifier():
    """Template matche mais montant absent → A_VERIFIER (#9)."""
    lignes = process_lot(
        [FIXTURES / "champ_manquant_montant.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "champ_manquant_montant.pdf"
    assert ligne.emetteur == "Masse"
    assert ligne.date == "15/03/2026"
    assert ligne.montant_ttc is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_date_invalide_a_verifier():
    """Date capturée hors format valide → A_VERIFIER (#9)."""
    lignes = process_lot(
        [FIXTURES / "date_invalide.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "date_invalide.pdf"
    assert ligne.emetteur == "Masse"
    assert ligne.date is None
    assert ligne.montant_ttc == "100,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_montant_non_decimal_a_verifier(tmp_path):
    """Montant capturé mais non décimal plausible → A_VERIFIER (#9)."""
    # Regex plus large que masse.yml pour capturer un jeton non numérique (N/A).
    (tmp_path / "masse.yml").write_text(
        "issuer: Masse\n"
        "keywords:\n"
        "  - MASSE NANTES\n"
        "  - maison-masse\n"
        "fields:\n"
        "  date: 'Date\\s+(\\d{2}/\\d{2}/\\d{4})'\n"
        "  amount: 'TOTAL TTC en EURO\\s+(\\S+)'\n"
        "options:\n"
        "  date_formats:\n"
        "    - '%d/%m/%Y'\n"
        "  decimal_separator: ','\n",
        encoding="utf-8",
    )

    lignes = process_lot(
        [FIXTURES / "montant_non_decimal.pdf"],
        tmp_path,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "montant_non_decimal.pdf"
    assert ligne.emetteur == "Masse"
    assert ligne.date == "15/03/2026"
    assert ligne.montant_ttc is None
    assert ligne.statut == "A_VERIFIER"


def test_correction_manuelle_refletee_dans_export_sans_modifier_templates():
    """Correction éphémère émetteur/date/montant → CSV mis à jour, templates intacts (#10)."""
    templates_before = {p.name: p.read_bytes() for p in TEMPLATES.glob("*.yml")}

    lignes = process_lot(
        [CORPUS / "Masse 22 Juillet 26.pdf"],
        TEMPLATES,
    )
    corrigee = corriger_ligne(
        lignes[0],
        emetteur="Masse corrigé",
        date="01/01/2026",
        montant_ttc="1,23",
    )

    assert export_csv([corrigee]) == (
        "fichier;emetteur;date;montant_ttc;statut\n"
        "Masse 22 Juillet 26.pdf;Masse corrigé;01/01/2026;1,23;OK\n"
    )
    assert {p.name: p.read_bytes() for p in TEMPLATES.glob("*.yml")} == templates_before


def test_correction_manuelle_partielle_ne_touche_que_les_champs_fournis():
    """On peut corriger un seul champ ; les autres restent (#10)."""
    lignes = process_lot(
        [CORPUS / "Masse 22 Juillet 26.pdf"],
        TEMPLATES,
    )
    corrigee = corriger_ligne(lignes[0], montant_ttc="999,99")

    assert export_csv([corrigee]) == (
        "fichier;emetteur;date;montant_ttc;statut\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;999,99;OK\n"
    )

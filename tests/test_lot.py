import shutil
from pathlib import Path

from app.csv_export import export_csv
from app.lot import corriger_ligne, process_lot
from app.models import TYPE_AVOIR, TYPE_FACTURE

CORPUS = Path(__file__).resolve().parents[1] / "private_corpus"
CORPUS_2 = Path(__file__).resolve().parents[1] / "private_corpus_2"
TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _montant_fr(ligne):
    return ligne.montant_ht.format_fr() if ligne.montant_ht else None


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
    assert _montant_fr(ligne) == "751,95"
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
    assert _montant_fr(ligne) == "349,20"
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
    assert _montant_fr(ligne) == "582,02"
    assert ligne.statut == "OK"


def test_lot_devaud_10_juillet_montant_ht_avec_separateur_milliers():
    """Total HT avec espace milliers (ex. 1 095,38) → montant HT OK (#67)."""
    lignes = process_lot(
        [CORPUS / "Devaud 10 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Devaud 10 Juillet 26.pdf"
    assert ligne.emetteur == "Devaud"
    assert ligne.date == "10/07/2026"
    assert _montant_fr(ligne) == "1095,38"
    assert ligne.statut == "OK"


def test_lot_aluplast_montant_ht_pas_ttc_ni_tva():
    lignes = process_lot(
        [CORPUS / "Aluplast 13 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Aluplast 13 Juillet 26.pdf"
    assert ligne.emetteur == "Aluplast"
    assert ligne.date == "13/07/2026"
    assert _montant_fr(ligne) == "269,50"
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
    assert _montant_fr(facture) == "1 751,30".replace(" ", "")
    assert facture.statut == "OK"
    assert facture.type_document == TYPE_FACTURE
    assert avoir.fichier == "Hennequin AVOIR 10 Juillet 26.pdf"
    assert avoir.emetteur == "Hennequin"
    assert avoir.date == "10/07/2026"
    assert _montant_fr(avoir) == "-1 350,50".replace(" ", "")
    assert avoir.statut == "OK"
    assert avoir.type_document == TYPE_AVOIR


def test_lot_veolia_factures_et_avoir_meme_template():
    lignes = process_lot(
        [
            CORPUS_2 / "Véolia eaux 23 Juillet 26.pdf",
            CORPUS / "Véolia eaux Avoir 22 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 2
    facture, avoir = lignes
    assert facture.fichier == "Véolia eaux 23 Juillet 26.pdf"
    assert facture.emetteur == "Veolia Eau"
    assert facture.date == "23/07/2026"
    assert _montant_fr(facture) == "1736,04"
    assert facture.statut == "OK"
    assert facture.type_document == TYPE_FACTURE
    assert avoir.fichier == "Véolia eaux Avoir 22 Juillet 26.pdf"
    assert avoir.emetteur == "Veolia Eau"
    assert avoir.date == "22/07/2026"
    assert _montant_fr(avoir) == "-1070,27"
    assert avoir.statut == "OK"
    assert avoir.type_document == TYPE_AVOIR


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
    assert [_montant_fr(ligne) for ligne in lignes] == ["2448,31", "3513,46", "-32,50"]
    assert all(ligne.statut == "OK" for ligne in lignes)
    assert [ligne.type_document for ligne in lignes] == [
        TYPE_FACTURE,
        TYPE_FACTURE,
        TYPE_AVOIR,
    ]


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
    assert [_montant_fr(l) for l in lignes] == ["751,95", "203,29", "623,15"]
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
    assert _montant_fr(ligne) == "120,00"
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
    assert _montant_fr(lignes[0]) == "227,27"
    assert lignes[1].date == "01/07/2026"
    assert _montant_fr(lignes[1]) == "547,57"
    assert lignes[2].date == "19/07/2026"
    assert _montant_fr(lignes[2]) == "11,00"


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
    assert ligne.montant_ht is None
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
    assert _montant_fr(ligne) == "55,50"
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
    assert _montant_fr(ligne) == "100,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_ht_vs_ttc_retient_ht():
    """Concurrence HT vs TTC → le HT est retenu (#40)."""
    lignes = process_lot(
        [FIXTURES / "filet_ht_vs_ttc.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert _montant_fr(ligne) == "80,00"
    assert _montant_fr(ligne) != "100,00"
    assert ligne.statut == "A_VERIFIER"


def test_lot_filet_montants_ht_ambigus_montant_vide():
    """Plusieurs montants HT distincts → montant vide (#40)."""
    lignes = process_lot(
        [FIXTURES / "filet_montants_ambigus.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.date == "01/07/2026"
    assert ligne.montant_ht is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_acr_template_ok():
    lignes = process_lot([CORPUS / "ACR 1 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "ACR"
    assert ligne.date == "01/07/2026"
    assert _montant_fr(ligne) == "120,00"
    assert ligne.statut == "OK"


def test_lot_spre_template_ok():
    lignes = process_lot([CORPUS / "SPRE 1er Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "SPRE"
    assert ligne.date == "01/07/2026"
    assert _montant_fr(ligne) == "547,57"
    assert ligne.statut == "OK"


def test_lot_youtrust_template_ok():
    lignes = process_lot([CORPUS / "Youtrust 19 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Youtrust"
    assert ligne.date == "19/07/2026"
    assert _montant_fr(ligne) == "11,00"
    assert ligne.statut == "OK"


def test_lot_compagnie_deboucheurs_template_ok():
    compagnie = next(CORPUS.glob("Compagnie*Juillet*.pdf"))
    lignes = process_lot([compagnie], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Compagnie des Déboucheurs"
    assert ligne.date == "20/07/2026"
    assert _montant_fr(ligne) == "227,27"
    assert ligne.statut == "OK"


def test_lot_domaine_verzier_template_ok():
    lignes = process_lot([CORPUS / "Domaine Verzier 29 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Domaine Verzier"
    assert ligne.date == "29/07/2026"
    assert _montant_fr(ligne) == "956,60"
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
    assert [_montant_fr(l) for l in lignes] == ["186,78", "186,78"]
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
    assert [_montant_fr(l) for l in lignes] == ["166,40", "416,00"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_metro_deux_pdf_meme_template_ok():
    metro_paths = sorted(CORPUS.glob("M*tro*Juillet*.pdf"))
    assert len(metro_paths) == 2
    lignes = process_lot(metro_paths, TEMPLATES)
    assert len(lignes) == 2
    assert all(l.emetteur == "Métro" for l in lignes)
    assert [l.date for l in lignes] == ["01/07/2026", "08/07/2026"]
    assert [_montant_fr(l) for l in lignes] == ["1837,04", "2166,78"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_edf_deux_pdf_meme_template_ok():
    lignes = process_lot(
        [
            CORPUS_2 / "EDF Juillet 26.pdf",
            CORPUS_2 / "EDF Electricité 1er Juillet 26.pdf",
        ],
        TEMPLATES,
    )
    assert len(lignes) == 2
    assert [l.fichier for l in lignes] == [
        "EDF Juillet 26.pdf",
        "EDF Electricité 1er Juillet 26.pdf",
    ]
    assert all(l.emetteur == "EDF" for l in lignes)
    assert [l.date for l in lignes] == ["01/08/2026", "01/07/2026"]
    assert [_montant_fr(l) for l in lignes] == ["1027,78", "889,36"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_hotel_formule1_ocr_champs_mais_a_verifier():
    formule = next(CORPUS.glob("Hotel Formule*"))
    lignes = process_lot([formule], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == formule.name
    assert ligne.emetteur == "Hotel Formule 1"
    assert ligne.date == "05/07/2026"
    assert _montant_fr(ligne) == "30,91"
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
    assert _montant_fr(ligne) == "362,33"
    assert ligne.statut == "A_VERIFIER"


def test_lot_altagel_montant_avec_separateur_milliers():
    """1.008,33 ne doit pas être lu comme 100,00 (#montants milliers)."""
    lignes = process_lot(
        [CORPUS / "Altagel 20 Juillet 26.pdf"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Altagel 20 Juillet 26.pdf"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "20/07/2026"
    assert _montant_fr(ligne) == "955,76"
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
    assert _montant_fr(ligne) == "99,50"
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
    assert ligne.montant_ht is None
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
    assert _montant_fr(ligne) == "100,00"
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
        "  amount: 'TOTAL HT en EURO\\s+(\\S+)'\n"
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
    assert ligne.montant_ht is None
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
        montant_ht="1,23",
    )

    assert export_csv([corrigee]) == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Masse corrigé;1,23;1\n"
    )
    assert {p.name: p.read_bytes() for p in TEMPLATES.glob("*.yml")} == templates_before


def test_lot_image_png_template_connu_a_verifier():
    """Image avec Template : champs extraits, statut A_VERIFIER (OCR)."""
    lignes = process_lot(
        [FIXTURES / "scan_sans_texte.png"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "scan_sans_texte.png"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "15/03/2026"
    assert _montant_fr(ligne) == "99,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_image_jpg_sans_template_filet_a_verifier(tmp_path):
    """Image sans Template : filet date/montant, pas d'Émetteur."""
    lignes = process_lot(
        [FIXTURES / "detection_ambigue_masse_aluplast.jpg"],
        tmp_path,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "detection_ambigue_masse_aluplast.jpg"
    assert ligne.emetteur is None
    assert ligne.date == "12/03/2026"
    assert _montant_fr(ligne) == "55,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_image_illisible_champs_vides_a_verifier():
    lignes = process_lot(
        [FIXTURES / "rien_extractible.png"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur is None
    assert ligne.date is None
    assert ligne.montant_ht is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_heic_template_connu_a_verifier():
    lignes = process_lot(
        [FIXTURES / "scan_sans_texte.heic"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "scan_sans_texte.heic"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "15/03/2026"
    assert _montant_fr(ligne) == "99,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_mixte_pdf_natif_et_image_statuts_independants():
    lignes = process_lot(
        [
            CORPUS / "Masse 22 Juillet 26.pdf",
            FIXTURES / "scan_sans_texte.png",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 2
    pdf_ligne, image_ligne = lignes
    assert pdf_ligne.fichier == "Masse 22 Juillet 26.pdf"
    assert pdf_ligne.statut == "OK"
    assert image_ligne.fichier == "scan_sans_texte.png"
    assert image_ligne.statut == "A_VERIFIER"


def test_lot_image_champ_manquant_a_verifier():
    lignes = process_lot(
        [FIXTURES / "champ_manquant_montant.png"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Masse"
    assert ligne.date == "15/03/2026"
    assert ligne.montant_ht is None
    assert ligne.statut == "A_VERIFIER"


def test_lot_image_detection_ambigue_filet_sans_emetteur(tmp_path):
    """≥2 templates matchent sur image → aucun appliqué ; filet préremplit."""
    shutil.copy(TEMPLATES / "masse.yml", tmp_path / "masse.yml")
    shutil.copy(TEMPLATES / "aluplast.yml", tmp_path / "aluplast.yml")

    lignes = process_lot(
        [FIXTURES / "detection_ambigue_masse_aluplast.png"],
        tmp_path,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur is None
    assert ligne.date == "12/03/2026"
    assert _montant_fr(ligne) == "55,50"
    assert ligne.statut == "A_VERIFIER"


def test_lot_image_date_invalide_a_verifier():
    lignes = process_lot(
        [FIXTURES / "date_invalide.png"],
        TEMPLATES,
    )

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Masse"
    assert ligne.date is None
    assert _montant_fr(ligne) == "100,00"
    assert ligne.statut == "A_VERIFIER"


def test_correction_manuelle_partielle_ne_touche_que_les_champs_fournis():
    """On peut corriger un seul champ ; les autres restent (#10)."""
    lignes = process_lot(
        [CORPUS / "Masse 22 Juillet 26.pdf"],
        TEMPLATES,
    )
    corrigee = corriger_ligne(lignes[0], montant_ht="999,99")

    assert export_csv([corrigee]) == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Masse;999,99;1\n"
    )


def test_lot_masse_classifie_facture():
    lignes = process_lot([CORPUS / "Masse 22 Juillet 26.pdf"], TEMPLATES)
    assert lignes[0].type_document == TYPE_FACTURE


def test_lot_aluplast_et_valrhona_pas_avoir_malgre_cgv():
    """Le verbe / mention CGV « avoir » ne doit pas classer une facture en AVOIR (#38)."""
    lignes = process_lot(
        [
            CORPUS / "Aluplast 13 Juillet 26.pdf",
            CORPUS / "Valrhona 1er Juillet 26.pdf",
            CORPUS / "Valrhona 20 Juillet 26.pdf",
        ],
        TEMPLATES,
    )
    assert [ligne.type_document for ligne in lignes] == [
        TYPE_FACTURE,
        TYPE_FACTURE,
        TYPE_FACTURE,
    ]


def test_lot_sans_marqueur_clair_classifie_facture():
    """Sans indice avoir (titre/nom) → FACTURE par défaut (#38)."""
    lignes = process_lot([FIXTURES / "rien_extractible.pdf"], TEMPLATES)
    assert lignes[0].type_document == TYPE_FACTURE
    assert lignes[0].statut == "A_VERIFIER"


def test_correction_manuelle_type_refletee_dans_export():
    lignes = process_lot([CORPUS / "Masse 22 Juillet 26.pdf"], TEMPLATES)
    corrigee = corriger_ligne(lignes[0], type_document=TYPE_AVOIR)
    csv = export_csv([corrigee])
    assert csv == "\ufeffemetteur;montant_ht;nb_documents\nMasse;751,95;1\n"


def test_lot_vbb_factures_et_avoir_meme_template():
    lignes = process_lot(
        [
            CORPUS_2 / "VBB 10 Juillet 26.pdf",
            CORPUS_2 / "VBB 17 Juillet 26.pdf",
            CORPUS_2 / "VBB 28 Juillet 26.pdf",
            CORPUS_2 / "VBB 31 Juillet 26.pdf",
            CORPUS_2 / "VBB Avoir 2 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 5
    assert all(ligne.emetteur == "VBB" for ligne in lignes)
    assert [ligne.date for ligne in lignes] == [
        "10/07/2026",
        "17/07/2026",
        "28/07/2026",
        "31/07/2026",
        "02/07/2026",
    ]
    assert [_montant_fr(ligne) for ligne in lignes] == [
        "111,13",
        "73,32",
        "103,71",
        "55,71",
        "-13,27",
    ]
    assert all(ligne.statut == "OK" for ligne in lignes)
    assert [ligne.type_document for ligne in lignes] == [
        TYPE_FACTURE,
        TYPE_FACTURE,
        TYPE_FACTURE,
        TYPE_FACTURE,
        TYPE_AVOIR,
    ]


def test_lot_vendee_crustaces_trois_pdf_meme_template_ok():
    lignes = process_lot(
        [
            CORPUS_2 / "Vendée crustacés 10 Juillet 26.pdf",
            CORPUS_2 / "Vendée crustacés 20 Juillet 26.pdf",
            CORPUS_2 / "Vendée crustacés 31 Juillet 26.pdf",
        ],
        TEMPLATES,
    )

    assert len(lignes) == 3
    assert all(ligne.emetteur == "Vendée crustacés" for ligne in lignes)
    assert [ligne.date for ligne in lignes] == [
        "10/07/2026",
        "20/07/2026",
        "31/07/2026",
    ]
    assert [_montant_fr(ligne) for ligne in lignes] == [
        "2025,14",
        "3974,24",
        "4307,60",
    ]
    assert all(ligne.statut == "OK" for ligne in lignes)


def test_lot_mercier_template_ok():
    lignes = process_lot([CORPUS_2 / "Mercier 31 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Mercier"
    assert ligne.date == "31/07/2026"
    assert _montant_fr(ligne) == "3702,15"
    assert ligne.statut == "OK"


def test_lot_nespresso_template_ok():
    lignes = process_lot([CORPUS_2 / "Nespresso 16 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Nespresso"
    assert ligne.date == "16/07/2026"
    assert _montant_fr(ligne) == "439,53"
    assert ligne.statut == "OK"


def test_lot_free_template_ok():
    lignes = process_lot([CORPUS_2 / "Free 1er août 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Free"
    assert ligne.date == "01/08/2026"
    assert _montant_fr(ligne) == "51,45"
    assert ligne.statut == "OK"


def test_lot_inexweb_social_et_compta_meme_template_ok():
    lignes = process_lot(
        [
            CORPUS_2 / "Inexweb social 31 Juillet 26.pdf",
            CORPUS_2 / "Inexweb compta 31 Juillet 26.pdf",
        ],
        TEMPLATES,
    )
    assert len(lignes) == 2
    assert all(l.emetteur == "Inexweb" for l in lignes)
    assert [l.date for l in lignes] == ["31/07/2026", "31/07/2026"]
    assert [_montant_fr(l) for l in lignes] == ["631,66", "669,01"]
    assert all(l.statut == "OK" for l in lignes)


def test_lot_erco_template_ok():
    lignes = process_lot([CORPUS_2 / "erco 16 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "ERCO"
    assert ligne.date == "16/07/2026"
    assert _montant_fr(ligne) == "331,64"
    assert ligne.statut == "OK"
    assert ligne.type_document == TYPE_FACTURE


def test_lot_maison_vito_template_ok():
    lignes = process_lot([CORPUS_2 / "Maison Vito 15 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Maison Vito"
    assert ligne.date == "15/07/2026"
    assert _montant_fr(ligne) == "114,00"
    assert ligne.statut == "OK"


def test_lot_la_poste_template_ok():
    lignes = process_lot([CORPUS_2 / "la Poste 9 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "La Poste"
    assert ligne.date == "09/07/2026"
    assert _montant_fr(ligne) == "17,14"
    assert ligne.statut == "OK"


def test_lot_hapi_facture_pas_avoir_malgre_cgv():
    lignes = process_lot([CORPUS_2 / "Hapi 5 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Hapi"
    assert ligne.date == "05/07/2026"
    assert _montant_fr(ligne) == "1200,00"
    assert ligne.statut == "OK"
    assert ligne.type_document == TYPE_FACTURE


def test_lot_compagnie_desserts_template_ok():
    lignes = process_lot(
        [CORPUS_2 / "Compagnie desserts 24 Juillet 26.pdf"],
        TEMPLATES,
    )
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.emetteur == "Compagnie des Desserts"
    assert ligne.date == "24/07/2026"
    assert _montant_fr(ligne) == "230,04"
    assert ligne.statut == "OK"


def test_lot_marche_aux_vins_template_ok():
    lignes = process_lot([CORPUS_2 / "Marché aux vins 31 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Marché aux vins 31 Juillet 26.pdf"
    assert ligne.emetteur == "Marché aux vins"
    assert ligne.date == "31/07/2026"
    assert _montant_fr(ligne) == "483,90"
    assert ligne.statut == "OK"


def test_lot_lofoten_template_ok():
    lignes = process_lot([CORPUS_2 / "Lofoten 13 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Lofoten 13 Juillet 26.pdf"
    assert ligne.emetteur == "Lofoten"
    assert ligne.date == "13/07/2026"
    assert _montant_fr(ligne) == "68,85"
    assert ligne.statut == "OK"


def test_lot_fincut_template_ok():
    lignes = process_lot([CORPUS_2 / "Fincut 21 Juillet 26.pdf"], TEMPLATES)
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "Fincut 21 Juillet 26.pdf"
    assert ligne.emetteur == "Fincut"
    assert ligne.date == "21/07/2026"
    assert _montant_fr(ligne) == "37,41"
    assert ligne.statut == "OK"


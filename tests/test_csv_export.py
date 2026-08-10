from app.amounts import MontantHt
from app.csv_export import export_csv
from app.models import TYPE_AVOIR, TYPE_FACTURE, LigneFacture


def test_export_csv_detail_format_excel_fr():
    csv = export_csv(
        [
            LigneFacture(
                fichier="Masse 22 Juillet 26.pdf",
                emetteur="Masse",
                date="22/07/2026",
                montant_ht=MontantHt.parse_fr("793,31"),
                statut="OK",
                type_document=TYPE_FACTURE,
            ),
            LigneFacture(
                fichier="Altagel 10 Juillet 26.pdf",
                emetteur="Altagel",
                date="10/07/2026",
                montant_ht=MontantHt.parse_fr("382,26"),
                statut="A_VERIFIER",
                type_document=TYPE_FACTURE,
            ),
        ]
    )

    assert csv == (
        "\ufeff"
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;793,31;OK;FACTURE\n"
        "Altagel 10 Juillet 26.pdf;Altagel;10/07/2026;382,26;A_VERIFIER;FACTURE\n"
    )


def test_export_csv_facture_avant_avoir_et_champs_vides():
    csv = export_csv(
        [
            LigneFacture(
                fichier="avoir.pdf",
                emetteur="Hennequin",
                date="10/07/2026",
                montant_ht=MontantHt.parse_fr("-1424,78"),
                statut="OK",
                type_document=TYPE_AVOIR,
            ),
            LigneFacture(
                fichier="incomplet.pdf",
                emetteur=None,
                date=None,
                montant_ht=None,
                statut="A_VERIFIER",
                type_document=TYPE_FACTURE,
            ),
        ]
    )

    assert csv.startswith("\ufeff")
    rows = csv.lstrip("\ufeff").strip().split("\n")
    assert rows[0] == "fichier;emetteur;date;montant_ht;statut;type"
    assert rows[1] == "incomplet.pdf;;;;A_VERIFIER;FACTURE"
    assert rows[2] == "avoir.pdf;Hennequin;10/07/2026;-1424,78;OK;AVOIR"

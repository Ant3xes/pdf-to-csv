from app.csv_export import export_csv
from app.models import TYPE_AVOIR, TYPE_FACTURE, LigneFacture


def test_export_csv_format_excel_fr():
    csv = export_csv(
        [
            LigneFacture(
                fichier="Masse 22 Juillet 26.pdf",
                emetteur="Masse",
                date="22/07/2026",
                montant_ht="793,31",
                statut="OK",
                type_document=TYPE_FACTURE,
            ),
            LigneFacture(
                fichier="Altagel 10 Juillet 26.pdf",
                emetteur="Altagel",
                date="10/07/2026",
                montant_ht="382,26",
                statut="A_VERIFIER",
                type_document=TYPE_FACTURE,
            ),
        ]
    )

    assert csv == (
        "fichier;emetteur;date;montant_ht;statut;type\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;793,31;OK;FACTURE\n"
        "Altagel 10 Juillet 26.pdf;Altagel;10/07/2026;382,26;A_VERIFIER;FACTURE\n"
    )


def test_export_csv_factures_avant_avoirs():
    csv = export_csv(
        [
            LigneFacture(
                fichier="Hennequin AVOIR 10 Juillet 26.pdf",
                emetteur="Hennequin",
                date="10/07/2026",
                montant_ht="-1424,78",
                statut="OK",
                type_document=TYPE_AVOIR,
            ),
            LigneFacture(
                fichier="Masse 22 Juillet 26.pdf",
                emetteur="Masse",
                date="22/07/2026",
                montant_ht="793,31",
                statut="OK",
                type_document=TYPE_FACTURE,
            ),
        ]
    )

    rows = csv.strip().split("\n")
    assert rows[0] == "fichier;emetteur;date;montant_ht;statut;type"
    assert rows[1].startswith("Masse 22 Juillet 26.pdf;")
    assert rows[2].startswith("Hennequin AVOIR 10 Juillet 26.pdf;")
    assert rows[2].endswith(";AVOIR")

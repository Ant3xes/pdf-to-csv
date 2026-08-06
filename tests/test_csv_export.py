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
                statut="OK",
                type_document=TYPE_FACTURE,
            ),
        ]
    )

    assert csv == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Altagel;382,26;1\n"
        "Masse;793,31;1\n"
    )


def test_export_csv_total_net_facture_et_avoir():
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

    assert csv.startswith("\ufeff")
    rows = csv.lstrip("\ufeff").strip().split("\n")
    assert rows[0] == "emetteur;montant_ht;nb_documents"
    assert rows[1] == "Hennequin;-1424,78;1"
    assert rows[2] == "Masse;793,31;1"

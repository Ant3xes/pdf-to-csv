from app.csv_export import export_csv
from app.models import LigneFacture


def test_export_csv_format_excel_fr():
    csv = export_csv(
        [
            LigneFacture(
                fichier="Masse 22 Juillet 26.pdf",
                emetteur="Masse",
                date="22/07/2026",
                montant_ttc="793,31",
                statut="OK",
            ),
            LigneFacture(
                fichier="Altagel 10 Juillet 26.pdf",
                emetteur="Altagel",
                date="10/07/2026",
                montant_ttc="382,26",
                statut="A_VERIFIER",
            ),
        ]
    )

    assert csv == (
        "fichier;emetteur;date;montant_ttc;statut\n"
        "Masse 22 Juillet 26.pdf;Masse;22/07/2026;793,31;OK\n"
        "Altagel 10 Juillet 26.pdf;Altagel;10/07/2026;382,26;A_VERIFIER\n"
    )

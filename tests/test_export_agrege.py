import pytest

from app.amounts import MontantHt
from app.export_agrege import (
    agreger_par_emetteur,
    export_csv_agrege,
    valider_export,
)
from app.models import TYPE_AVOIR, TYPE_FACTURE, LigneFacture


def _ligne(**kwargs) -> LigneFacture:
    defaults = {
        "fichier": "f.pdf",
        "emetteur": "Masse",
        "date": "01/01/2026",
        "montant_ht": "100,00",
        "statut": "OK",
        "type_document": TYPE_FACTURE,
    }
    defaults.update(kwargs)
    montant = defaults.get("montant_ht")
    if isinstance(montant, str):
        defaults["montant_ht"] = MontantHt.parse_fr(montant)
    return LigneFacture(**defaults)


def test_agreger_plusieurs_factures_meme_emetteur():
    totaux = agreger_par_emetteur(
        [
            _ligne(fichier="a.pdf", montant_ht="751,95"),
            _ligne(fichier="b.pdf", montant_ht="203,29"),
        ]
    )

    assert len(totaux) == 1
    assert totaux[0].emetteur == "Masse"
    assert totaux[0].montant_ht == "955,24"
    assert totaux[0].nb_documents == 2


def test_agreger_total_net_facture_et_avoir():
    totaux = agreger_par_emetteur(
        [
            _ligne(
                fichier="facture.pdf",
                emetteur="Hennequin",
                montant_ht="1751,30",
                type_document=TYPE_FACTURE,
            ),
            _ligne(
                fichier="avoir.pdf",
                emetteur="Hennequin",
                montant_ht="-1350,50",
                type_document=TYPE_AVOIR,
            ),
        ]
    )

    assert len(totaux) == 1
    assert totaux[0].emetteur == "Hennequin"
    assert totaux[0].montant_ht == "400,80"
    assert totaux[0].nb_documents == 2


def test_agreger_montant_vide_ou_invalide_compte_comme_zero():
    totaux = agreger_par_emetteur(
        [
            _ligne(montant_ht="100,00"),
            _ligne(fichier="b.pdf", montant_ht=None),
            _ligne(fichier="c.pdf", montant_ht="pas-un-nombre"),
        ]
    )

    assert totaux[0].montant_ht == "100,00"
    assert totaux[0].nb_documents == 3


def test_agreger_tri_alphabetique_emetteurs():
    totaux = agreger_par_emetteur(
        [
            _ligne(emetteur="Zorro"),
            _ligne(emetteur="Aluplast", fichier="b.pdf"),
        ]
    )

    assert [t.emetteur for t in totaux] == ["Aluplast", "Zorro"]


def test_export_csv_agrege_format_fr():
    csv = export_csv_agrege(
        [
            _ligne(emetteur="Masse", montant_ht="793,31"),
            _ligne(fichier="b.pdf", emetteur="Altagel", montant_ht="382,26"),
        ]
    )

    assert csv == (
        "\ufeff"
        "emetteur;montant_ht;nb_documents\n"
        "Altagel;382,26;1\n"
        "Masse;793,31;1\n"
    )


def test_export_csv_agrege_commence_par_bom_utf8():
    csv = export_csv_agrege([_ligne()])
    assert csv.startswith("\ufeff")


def test_valider_export_rejette_lot_vide():
    assert valider_export([]) == "Aucune ligne à exporter."


def test_valider_export_rejette_emetteur_manquant():
    erreur = valider_export([_ligne(emetteur=None)])

    assert erreur is not None
    assert "émetteur" in erreur.lower()


def test_valider_export_rejette_a_verifier():
    erreur = valider_export([_ligne(statut="A_VERIFIER")])

    assert erreur is not None
    assert "vérifier" in erreur.lower()


def test_valider_export_rejette_statut_invalide():
    erreur = valider_export([_ligne(statut="VALIDE")])

    assert erreur is not None
    assert "statut" in erreur.lower()


def test_valider_export_rejette_ok_sans_date_ou_montant():
    assert valider_export([_ligne(date=None)]) is not None
    assert valider_export([_ligne(montant_ht="")]) is not None
    assert "montant" in (valider_export([_ligne(montant_ht=None)]) or "").lower()


def test_valider_export_accepte_lot_ok():
    assert valider_export([_ligne()]) is None

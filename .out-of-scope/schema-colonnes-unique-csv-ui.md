# Schéma de colonnes unique CSV + détail UI

Ce projet ne maintient pas une définition unique de colonnes partagée entre l’export CSV et le tableau de détail des factures dans l’interface.

## Why this is out of scope

L’export CSV et l’UI servent des contrats différents par conception (ADR 0004 — export agrégé par Émetteur) :

- le CSV contient **une ligne par Émetteur** avec `emetteur;montant_ht;nb_documents` ;
- l’interface conserve le **détail par Facture** (fichier, émetteur, date, montant HT, statut, type, actions).

Centraliser une seule liste de colonnes consommée à la fois par le CSV, le rendu du tableau et l’édition inline forcerait soit à réintroduire le détail fichier dans l’export, soit à appauvrir l’UI — les deux contredisent l’ADR.

Un éventuel DRY purement interne à l’UI (listes d’en-têtes / champs éditables côté front) est un sujet distinct, hors de cette décision.

## Prior requests

- #23 — « Standards : liste des colonnes CSV/tableau dupliquée dans 4 fichiers »

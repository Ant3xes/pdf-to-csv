# Export CSV détail et groupé (avec Statut)

Le contexte : l'utilisateur a besoin d'exporter un Lot même avec des Factures « À vérifier », soit en détail (une ligne par Facture), soit agrégé par Émetteur nommé. Les Factures sans Émetteur ne se prêtent pas à un total fournisseur fiable.

Décision :
- **Exporter détail** : CSV `fichier;emetteur;date;montant_ht;statut;type` (une ligne par Facture).
- **Exporter groupé** : CSV `emetteur;montant_ht;nb_documents;fichier;date;statut;type` — une ligne de total par Émetteur nommé ; les Factures **sans Émetteur** restent en **détail ligne à ligne** (colonnes fichier/date/statut/type renseignées).
- L'export n'est refusé que si le Lot est vide ou si un Statut est hors de `{OK, A_VERIFIER}`.
- S'il reste des Factures « À vérifier », une confirmation est demandée avant l'enregistrement.

Cette décision **remplace** ADR-0004 pour le gating lié au Statut, et complète le détail en restaurant un mode groupé optionnel.

## Consequences

- Deux boutons d'export dans l'UI ; `POST /api/export` accepte `mode=detail|agrege`.
- Les Avoirs restent des lignes distinctes en détail ; en groupé, ils contribuent au total net de leur Émetteur nommé.
- Les totaux par Émetteur restent aussi un affichage UI.

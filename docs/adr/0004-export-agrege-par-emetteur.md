# Export agrégé par Émetteur

Le contexte : l'export CSV alimente un suivi comptable par fournisseur. L'export listait une ligne par Facture ; l'utilisateur a besoin des totaux nets HT par Émetteur, pas du détail fichier par fichier.

Décision : le CSV exporté contient **une ligne par Émetteur** avec les colonnes `emetteur;montant_ht;nb_documents`. L'interface conserve le détail par Facture (une ligne par fichier déposé) avec regroupement visuel et totaux par Émetteur. L'export est bloqué si une Facture n'a pas d'Émetteur ou est encore « À vérifier » ; les montants HT vides ou invalides comptent comme 0 dans l'agrégation.

## Consequences

- Breaking change du contrat CSV : plus de colonnes `fichier`, `date`, `statut`, `type` à l'export.
- Le total net par Émetteur additionne Factures et Avoirs (montants négatifs inclus).
- La validation d'export est dupliquée côté client (UX) et serveur (autoritaire).

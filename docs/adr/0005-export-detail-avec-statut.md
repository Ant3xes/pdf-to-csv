# Export CSV détail par Facture (avec Statut)

Le contexte : l'export CSV agrégé par Émetteur (ADR-0004) bloquait le téléchargement tant qu'une Facture était « À vérifier », et ne portait aucun Statut par ligne. L'utilisateur a besoin d'exporterter le Lot même avec des lignes douteuses, en les distinguant dans le fichier.

Décision : le CSV exporté contient **une ligne par Facture** avec les colonnes `fichier;emetteur;date;montant_ht;statut;type`. Les valeurs de `statut` sont `OK` et `A_VERIFIER`. L'export n'est refusé que si le Lot est vide ou si un Statut est hors de ces deux valeurs. Après le clic « Exporter CSV », s'il reste des Factures « À vérifier », l'interface prévient l'utilisateur puis télécharge quand même. L'interface conserve le regroupement visuel et les totaux par Émetteur.

Cette décision **remplace** ADR-0004 pour la forme du fichier exporté et le gating lié au Statut.

## Consequences

- Breaking change du contrat CSV : retour au détail par Facture ; plus d'agrégat `emetteur;montant_ht;nb_documents` à l'export.
- Les Avoirs restent des lignes distinctes (`type=AVOIR`, montants HT négatifs).
- La validation d'export reste dupliquée côté client (UX / avertissement) et serveur (autoritaire sur les rejets restants).
- Les totaux par Émetteur restent un affichage UI uniquement.

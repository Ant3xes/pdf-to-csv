# Montant HT à la place du montant TTC

Le contexte : l'export CSV alimente un suivi comptable basé sur les totaux hors taxes. L'application extrayait et exportait le montant TTC, ce qui forçait des corrections manuelles systématiques.

Décision : remplacer entièrement le champ `montant_ttc` par `montant_ht` (modèle, UI, CSV, templates, filet générique). Aucune coexistence des deux colonnes. Aucun calcul dérivé HT ← TTC (division par taux de TVA) — uniquement extraction regex déterministe, alignée sur ADR 0001. Si le total HT n'est pas extractible de façon fiable, le champ reste vide et le statut « À vérifier ».

## Consequences

- Breaking change du contrat CSV : colonne `montant_ht`.
- Les fournisseurs qui n'affichent qu'un « Net à payer » TTC sans total HT explicite échoueront plus souvent à l'extraction — comportement voulu (prudence > mauvais montant).
- Les templates et le filet générique doivent cibler des libellés HT et exclure TTC/TVA.

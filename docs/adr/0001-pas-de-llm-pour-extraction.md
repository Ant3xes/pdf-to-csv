# Pas de LLM/IA pour l'extraction des champs de facture

Le contexte : extraire émetteur, date et montant TTC depuis des factures PDF multi-fournisseurs aux layouts très variés — une tâche que des LLM récents géreraient facilement. Décision : extraction 100% déterministe (regex + templates par fournisseur, façon `invoice2data`), sans aucun appel à un LLM ou une API cloud d'extraction. Raison : les factures sont des données financières sensibles, et le coût/la dépendance à une API tierce (tokens, disponibilité, confidentialité) sont jugés inacceptables pour ce cas d'usage local et mono-utilisateur.

## Consequences

- Chaque nouveau fournisseur récurrent nécessite la création manuelle d'un template YAML — pas de généralisation automatique face à un layout inédit.
- Un fournisseur sans template va systématiquement en fallback manuel (voir `CONTEXT.md`), sans dégradation progressive possible comme le permettrait un LLM.
- Cette décision peut être révisée en V2 si les templates s'avèrent insuffisants à l'usage (voir "Hors scope" dans `PROJET_FACTURES_PDF_TO_CSV.md`), mais reste le principe par défaut du projet.

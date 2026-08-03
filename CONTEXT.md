# Convertisseur de Factures PDF vers CSV

Application locale qui convertit des factures PDF multi-fournisseurs en un CSV exploitable, par extraction déterministe (règles/regex + templates), sans LLM.

## Language

**Facture**:
Correspond toujours exactement à un PDF déposé par l'utilisateur : 1 PDF = 1 facture = 1 ligne dans le CSV exporté. Jamais plusieurs factures distinctes dans un même PDF, jamais une facture répartie sur plusieurs PDF. Les documents internes au PDF (bons de livraison, pages multiples) ne créent jamais de lignes CSV supplémentaires.

**Émetteur**:
Le nom de la société qui facture, tel qu'il figure dans le champ `issuer` du template qui a matché. C'est un libellé fixe associé au template — jamais une valeur extraite par regex depuis le texte de la facture. Sans template correspondant, l'émetteur n'a aucune valeur automatique et doit être saisi manuellement.

**Fournisseur**:
L'entité identifiée par les mots-clés de détection d'un template. Relation stricte 1:1 avec **Template** : un fournisseur a au plus un template actif à la fois. Si sa mise en page change, le template existant est édité/remplacé — pas de coexistence de plusieurs versions pour un même fournisseur.

**Template**:
Fichier YAML associant un **Fournisseur** (issuer + mots-clés de détection) à des règles d'extraction (regex) pour les champs `date` et `amount` uniquement. Ajouter un fournisseur ne doit nécessiter que l'ajout d'un fichier template, sans toucher au code.

**Statut**:
Valeur binaire portée par chaque facture : `OK` ou `À vérifier` (encodée `A_VERIFIER` dans le CSV exporté — même statut, deux représentations). Le CSV n'expose pas la raison ; si elle est affichée, c'est uniquement dans l'interface.

**Détection ambiguë**:
Se produit quand les mots-clés de plusieurs templates matchent le même texte de facture. Dans ce cas, aucun template n'est appliqué — la facture est traitée comme si aucun template ne correspondait.

**Lot**:
L'ensemble des PDF déposés ensemble par l'utilisateur en une session de traitement. Purement éphémère : aucune persistance entre les lancements de l'application, pas d'historique.

**Correction manuelle**:
Modification ponctuelle d'un champ pour une facture du lot en cours. Son effet est limité à la ligne CSV de cette facture — elle ne crée ni ne modifie jamais un template.
_Avoid_: Confondre avec la création/édition de template (action séparée, hors de l'UI en V1).

## Déclencheurs du statut "À vérifier"

Au moins un des cas suivants suffit à marquer une facture "À vérifier" :

1. Aucun template ne correspond à la facture.
2. **Détection ambiguë** (plusieurs templates matchent) — aucun n'est appliqué.
3. Un champ obligatoire est manquant après extraction.
4. La date extraite ne correspond à aucun format valide.
5. Le montant extrait ne correspond à aucun nombre décimal plausible.
6. Le texte source provient de l'OCR — systématique, indépendamment du succès apparent de l'extraction, par principe de prudence (l'OCR est structurellement moins fiable que le texte natif).

## Exemple de dialogue

> **Dev** : Si une facture Aluplast a un layout légèrement différent cette fois, mais que le template Aluplast matche quand même par erreur sur un mauvais total, on la marque comment ?
> **Expert métier** : Si la date ou le montant extrait ne ressemble à rien de plausible, "À vérifier" automatiquement — pas besoin d'attendre que ce soit un nouveau fournisseur pour douter du résultat.
> **Dev** : Et si je corrige le montant à la main dans le tableau ?
> **Expert métier** : Ça corrige juste cette ligne pour cet export. Ça ne touche pas le template Aluplast — si son layout a vraiment changé durablement, il faut éditer le fichier YAML à part.
> **Dev** : Et un fournisseur jamais vu, sans aucun template ?
> **Expert métier** : Pas d'émetteur auto-rempli, tu le tapes toi-même. Le template, si besoin, c'est un travail séparé — pas depuis l'UI, pas en V1.

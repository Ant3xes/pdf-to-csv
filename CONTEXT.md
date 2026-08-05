# Convertisseur de Factures PDF vers CSV

Application locale qui convertit des factures PDF multi-fournisseurs en un CSV exploitable, par extraction déterministe (règles/regex + templates), sans LLM.

## Language

**Facture**:
Correspond toujours exactement à un fichier déposé par l'utilisateur (PDF ou image JPG/PNG/HEIC) : 1 fichier = 1 facture = 1 ligne dans le CSV exporté. Jamais plusieurs factures distinctes dans un même fichier, jamais une facture répartie sur plusieurs fichiers. Les documents internes au PDF (bons de livraison, pages multiples) ne créent jamais de lignes CSV supplémentaires. Un **Avoir** est une facture au sens du pipeline (même règle 1 fichier = 1 ligne).

**Avoir**:
Document de crédit émis par un **Fournisseur** (remboursement, correction). Traité comme une **Facture** dans le pipeline (même extraction, même statut, même ligne CSV), mais identifié et présenté distinctement dans l'interface et l'export via le champ `type` (`AVOIR`). Le montant HT d'un avoir représente le crédit (pas une facture « positive » ordinaire). Classification : marqueurs documentaires (titre / nom de fichier « AVOIR », « votre avoir », etc.) — en cas de doute, défaut **Facture**, jamais Avoir par défaut.
_Avoid_: Traiter l'avoir comme un type hors pipeline, ou l'exclure silencieusement de l'export. Classer en Avoir sur le simple verbe « avoir » ou une mention CGV.

**Émetteur**:
Le nom de la société qui facture, tel qu'il figure dans le champ `issuer` du template qui a matché. C'est un libellé fixe associé au template — jamais une valeur extraite par regex depuis le texte de la facture. Sans template correspondant, l'émetteur n'a aucune valeur automatique et doit être saisi manuellement.

**Fournisseur**:
L'entité identifiée par les mots-clés de détection d'un template. Relation stricte 1:1 avec **Template** : un fournisseur a au plus un template actif à la fois. Si sa mise en page change, le template existant est édité/remplacé — pas de coexistence de plusieurs versions pour un même fournisseur. Plusieurs factures (ou avoirs) du même fournisseur dans un **Lot** ou dans le **Corpus** restent des lignes distinctes.

**Template**:
Fichier YAML associant un **Fournisseur** (issuer + mots-clés de détection) à des règles d'extraction (regex) pour les champs `date` et `amount` uniquement. Le champ `amount` extrait le **montant HT** (hors taxes), jamais le TTC. Ajouter un fournisseur ne doit nécessiter que l'ajout d'un fichier template, sans toucher au code.

**Statut**:
Valeur binaire portée par chaque facture : `OK` ou `À vérifier` (encodée `A_VERIFIER` dans le CSV exporté — même statut, deux représentations). Le CSV n'expose pas la raison ; si elle est affichée, c'est uniquement dans l'interface.

**Détection ambiguë**:
Se produit quand les mots-clés de plusieurs templates matchent le même texte de facture. Dans ce cas, aucun template n'est appliqué — la facture est traitée comme si aucun template ne correspondait.

**Lot**:
L'ensemble des fichiers déposés ensemble par l'utilisateur en une session de traitement (PDF et/ou images). Purement éphémère : aucune persistance entre les lancements de l'application, pas d'historique applicatif, pas de base de données de session.

**Corpus**:
Jeu de documents réels fournis pour concevoir les templates et valider le pipeline. Ce n'est pas une base de données applicative : c'est un dossier de fichiers d'exemple sur disque. Le corpus de référence du projet est le dossier `private_corpus/`.
_Avoid_: « base de données » pour désigner ce dossier — réserver ce terme à une éventuelle persistance applicative (hors scope V1).

**Quittance**:
Document de loyer / occupation (ex. [locataire], [locataire]), distinct d'une **Facture** fournisseur. Hors scope V1 : non traité par le pipeline d'extraction facture, même s'il figure dans le **Corpus**.
_Avoid_: Confondre quittance et facture ; ne pas créer de template « quittance » en V1.

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
> **Dev** : Le fichier « Hennequin AVOIR » et la quittance [locataire] en .jpg, on les traite comment ?
> **Expert métier** : L'avoir Hennequin, c'est une facture : une ligne CSV, même pipeline. La quittance [locataire], ce n'est pas une facture fournisseur — hors V1, même si elle est dans le corpus.

# Projet : Convertisseur de Factures PDF vers CSV

> Vocabulaire du domaine et décisions détaillées : voir [`CONTEXT.md`](./CONTEXT.md) et [`docs/adr/`](./docs/adr/).

## Contexte et objectif

Application locale, simple et user-friendly permettant de convertir des factures PDF (multi-fournisseurs, formats variés) en un fichier CSV exploitable (ouvrable dans Excel), **sans utiliser de LLM/IA** (pas de consommation de tokens, pas de dépendance cloud obligatoire).

L'utilisateur final n'est pas technique : l'interface doit être en drag & drop, simple, avec retour visuel clair.

## Contraintes fonctionnelles

- **Entrée** : PDF natifs (texte sélectionnable) ET PDF scannés/images (nécessitant OCR).
- **Multi-fournisseurs** : chaque facture peut avoir un layout complètement différent.
- **Volumétrie** : quelques dizaines de factures par lot.
- **Sortie** : un fichier CSV (une ligne par facture), ouvrable dans Excel.
- **Champs à extraire** :
  - Émetteur (nom de la société qui facture)
  - Date de la facture
  - Montant Total TTC
- **Fallback** : si l'extraction échoue ou est incertaine, afficher la facture à l'utilisateur pour saisie manuelle (pas de blocage silencieux).
- **Pas de LLM** : extraction basée sur règles/regex + templates par fournisseur (approche déterministe façon `invoice2data`) — voir [ADR-0001](./docs/adr/0001-pas-de-llm-pour-extraction.md).
- **OCR en fallback** : si le PDF ne contient pas de texte natif exploitable, basculer automatiquement sur OCR (Tesseract) avant d'appliquer les mêmes règles d'extraction.

## Architecture technique proposée

```
[Drag & drop PDF] 
      |
      v
[1. Extraction texte natif] --(texte vide/insuffisant)--> [2. OCR fallback (Tesseract)]
      |                                                              |
      v______________________________________________________________v
[3. Détection fournisseur (keywords dans le texte)]
      |
      v
[4. Application du template YAML correspondant (regex par champ)]
      |
      v
[5. Si échec ou champ manquant --> Interface de saisie manuelle]
      |
      v
[6. Agrégation des résultats --> Export CSV]
```

### Stack technique recommandée

| Composant | Outil | Rôle |
|---|---|---|
| Extraction texte PDF natif | `pdfplumber` ou `pdftotext` (poppler) | Extraire le texte brut des PDF non scannés |
| OCR fallback | `pytesseract` + `pdf2image` | Extraire le texte des PDF scannés/images |
| Extraction structurée | `invoice2data` (templates YAML + regex) | Détecter le fournisseur et extraire les champs sans IA |
| Interface | Flask + JS (drag & drop natif, édition inline) | UI simple pour l'utilisateur final — voir [ADR-0002](./docs/adr/0002-interface-flask-js.md) |
| Export | `pandas` | Agrégation des résultats et export CSV uniquement |

## Corpus de référence : `private_corpus/`

Le corpus réel du projet vit dans [`private_corpus/`](./private_corpus/) (dossier de fichiers sur disque — **pas** une base de données applicative ; voir **Corpus** dans [`CONTEXT.md`](./CONTEXT.md)).

Inventaire (≈ 30 fichiers, juillet 2026) :

| Fournisseur / document | Fichiers | Notes |
|---|---|---|
| ACR | 1 PDF | |
| Altagel | 2 PDF | Scan / OCR obligatoire (cas de référence historique) |
| Aluplast | 1 PDF | Cas de référence historique |
| Compagnie déboucheurs | 1 PDF | |
| Devaud | 1 PDF | Cas de référence historique (texte fusionné, multi-pages) |
| Domaine Verzier | 1 PDF | |
| Domaine des Jumeaux | 3 PDF | Dont un doublon nommé « copie » — 1 fichier = 1 ligne si déposé |
| Hennequin | 1 facture + 1 **avoir** | L'avoir est une Facture au sens du pipeline |
| Hotel Formule 1 | 1 PDF | Extension `.PDF` (casse à tolérer) |
| L'Anse du Piquet | 2 PDF | |
| Masse | 3 PDF | Cas de référence historique |
| Métro | 2 PDF | |
| SPRE | 1 PDF | |
| Valrhona | 2 PDF | |
| Véolia eaux | 1 **avoir** | |
| Vives eaux | 2 factures + 1 **avoir** | |
| Youtrust | 1 PDF | |
| Quittance [locataire] | 1 `.heic` | **Hors scope V1** (pas une Facture) |
| Quittance [locataire] | 1 `.jpg` | **Hors scope V1** (pas une Facture) |

### Cas de référence historiques (smoke tests prioritaires)

Ces 5 cas restent le premier jeu de validation du pipeline (fichiers présents dans le corpus) :

1. **Masse** — PDF natif, tableau multi-lignes, TVA multi-taux (5,5%), total TTC clairement libellé "TOTAL TTC en EURO".
2. **Domaine des Jumeaux** — PDF natif, une seule ligne produit, mentions légales collées au texte (peu d'espacement), total "Net à payer".
3. **Devaud** — PDF natif mais texte extrait sans espaces entre mots par endroits, facture multi-pages avec plusieurs bons de livraison, total final "NET A PAYER".
4. **Aluplast** — PDF natif, tableau + ligne "frais de port" séparée, bloc Total HT/TVA/TTC dense sans labels très explicites.
5. **Altagel** — **PDF scanné (image)**, nécessite obligatoirement l'OCR, tableau + totalisation par famille de produits, total "NET A PAYER".

Objectif V1 : un template YAML par fournisseur **récurrent** du corpus (hors quittances) ; les 5 cas ci-dessus sont le critère de « pipeline OK », le reste du corpus élargit la couverture.

## Structure de template attendue (invoice2data, exemple)

```yaml
issuer: Aluplast
keywords:
  - Aluplast
  - ZA La Prévôté
fields:
  date: (\d{2}/\d{2}/\d{2})\s*Conditions de règlement
  amount: Total TTC.*?(\d+[,.]\d{2})
options:
  currency: EUR
  date_formats:
    - '%d/%m/%y'
  decimal_separator: ','
```

Un template YAML doit être créé par fournisseur récurrent. Utiliser le mode debug de `invoice2data` pour visualiser le texte brut extrait avant d'écrire les regex.

## Comportement attendu de l'application

1. L'utilisateur dépose un ou plusieurs PDF dans la zone drag & drop.
2. Pour chaque PDF :
   - Tenter l'extraction de texte natif.
   - Si le texte est vide ou insuffisant (< seuil de caractères), basculer sur OCR.
   - Détecter le fournisseur via les templates disponibles (mots-clés). Si plusieurs templates matchent à la fois (détection ambiguë), n'en appliquer aucun.
   - Si un seul template correspond : reprendre l'émetteur depuis le champ `issuer` du template (valeur fixe, jamais extraite par regex), et extraire date + montant TTC via regex.
   - Marquer la facture "À vérifier" si : aucun template ne correspond, détection ambiguë, un champ obligatoire est manquant, la date ne matche aucun format valide, le montant ne correspond à aucun nombre décimal plausible, **ou si le texte source provient de l'OCR** (systématique, indépendamment du succès de l'extraction).
3. Afficher un tableau récapitulatif à l'utilisateur avec :
   - Nom du fichier
   - Émetteur détecté
   - Date détectée
   - Montant TTC détecté
   - Statut (OK / À vérifier)
4. Permettre la correction manuelle inline des champs marqués "À vérifier". Cette correction est éphémère : elle ne modifie que la ligne CSV de la facture concernée, jamais un template (créer un template à partir d'une correction est repoussé en V2 — voir "Hors scope").
5. Bouton d'export : génère un fichier CSV avec une ligne par facture, colonnes : `fichier, emetteur, date, montant_ttc, statut`. Aucune persistance entre les lancements de l'application (pas d'historique, pas de base de données applicative — le dossier `private_corpus/` est un corpus de fichiers, pas un stockage de session).

## Format de sortie CSV attendu

```csv
fichier;emetteur;date;montant_ttc;statut
Masse-22-Juillet-26.pdf;Masse;22/07/2026;793,31;OK
Domaine-des-jumeaux-4-Juillet-26-2.pdf;Domaine des Jumeaux;04/07/2026;419,04;OK
devaud-20-Juillet-26-3.pdf;Devaud;20/07/2026;615,68;OK
Aluplast-13-Juillet-26-4.pdf;Aluplast;13/07/2026;323,40;OK
Altagel-10-Juillet-26-5.pdf;Altagel;10/07/2026;382,26;A_VERIFIER
```

- Séparateur de champs : point-virgule (`;`) — convention CSV locale FR, reconnue nativement par Excel FR, et nécessaire car le séparateur décimal est la virgule.
- Séparateur décimal : virgule (ex: `793,31`), cohérent avec Excel FR et la locale des factures.
- Dates au format `JJ/MM/AAAA`.
- Montants en nombre (pas de symbole €).
- `statut` reste binaire (`OK` / `A_VERIFIER`) — pas de colonne "raison" dans le CSV exporté (voir `CONTEXT.md`).

## Étapes de développement suggérées (pour Claude Code)

1. **Setup projet** : structure de dossiers (`app/`, `templates/`, `tests/`), corpus déjà présent dans `private_corpus/`, dépendances (`requirements.txt` : `pdfplumber`, `pytesseract`, `pdf2image`, `invoice2data`, `pandas`, `flask`).
2. **Module extraction texte** : fonction `extract_text(pdf_path) -> str` avec fallback OCR automatique si texte natif insuffisant.
3. **Module détection + extraction structurée** : intégration `invoice2data` avec dossier de templates YAML personnalisés.
4. **Créer les templates YAML** à partir du corpus `private_corpus/` : d'abord les 5 cas de référence (Masse, Domaine des Jumeaux, Devaud, Aluplast, Altagel), puis élargir aux autres fournisseurs récurrents (y compris les avoirs, traités comme des factures).
5. **Module fallback manuel** : structure de données pour marquer les champs manquants/incertains et permettre correction utilisateur.
6. **Interface Flask + JS** : zone drag & drop multi-fichiers, tableau de résultats éditable inline, bouton export CSV — voir [ADR-0002](./docs/adr/0002-interface-flask-js.md).
7. **Export CSV** : génération finale via `pandas.DataFrame.to_csv(sep=';', decimal=',')`.
8. **Tests** : valider le pipeline sur les 5 cas de référence, puis sur un échantillon élargi du corpus (plusieurs factures par fournisseur, avoirs) ; vérifier émetteurs / dates / montants.

## Points d'attention techniques

- Le PDF "Altagel" est un scan pur : sans OCR, aucune extraction ne fonctionnera dessus. Vérifier la disponibilité de Tesseract sur la machine cible (binaire système, pas juste le wrapper Python).
- Le PDF "Devaud" a du texte fusionné sans espaces par endroits : prévoir des regex tolérantes ou une normalisation du texte (insertion d'espaces avant les majuscules après un chiffre, etc.) si besoin.
- Le PDF "Aluplast" a plusieurs montants proches (Total HT, TVA, Total TTC) sur des lignes denses : bien tester la regex du montant pour ne pas capturer le mauvais nombre.
- Les **avoirs** du corpus (Hennequin, Véolia eaux, Vives eaux) utilisent souvent des libellés différents (« AVOIR », totaux de crédit) : prévoir des regex / mots-clés adaptés dans le même template fournisseur, ou marquer "À vérifier" si le montant n'est pas fiable.
- Tolérer la casse des extensions (`.pdf` / `.PDF`) à l'entrée.
- Prévoir un seuil de confiance simple (ex: si la date extraite ne matche pas un format valide, ou si le montant ne correspond à aucun nombre décimal plausible, marquer automatiquement en "À vérifier").
- Garder le système extensible : ajouter un nouveau fournisseur doit juste nécessiter l'ajout d'un fichier YAML, sans toucher au code.

## Hors scope (V1)

- Pas d'extraction des lignes de détail (articles/quantités) — uniquement les 3 champs globaux (émetteur, date, montant TTC).
- Pas d'intégration comptable/ERP directe.
- Pas de solution cloud/API dans cette première version (uniquement si nécessaire dans un second temps si les templates s'avèrent insuffisants — voir [ADR-0001](./docs/adr/0001-pas-de-llm-pour-extraction.md)).
- Pas de génération de template depuis l'UI à partir d'une correction manuelle (backlog V2) : en V1, corriger une facture ne crée ni ne modifie jamais de template.
- Pas de coexistence de plusieurs templates pour un même fournisseur (pas de versioning de templates) : un changement de mise en page se traite en éditant/remplaçant le template existant.
- Pas d'export Excel (.xlsx) natif — le CSV, ouvrable dans Excel, suffit.
- Pas de traitement des **quittances** ni des entrées non-PDF (`.heic`, `.jpg`, etc.) présentes dans le corpus — entrée V1 = PDF uniquement.

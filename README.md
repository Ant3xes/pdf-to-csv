# Convertisseur Factures

Application **locale** (macOS) qui convertit un lot de factures PDF ou images en un **CSV Excel-ready**, avec extraction **déterministe** (templates YAML + regex). Aucun LLM, aucun envoi cloud : les documents restent sur la machine.

---

## Pour l’utilisateur

### À quoi ça sert

Vous déposez plusieurs factures (ou avoirs) d’un mois. L’application :

1. Lit chaque fichier (texte PDF natif, ou OCR si le document est scanné / une image)
2. Identifie le fournisseur grâce à des modèles préconfigurés
3. Extrait la **date** et le **montant HT**
4. Affiche un tableau éditable pour corriger ce qui manque ou ce qui est douteux
5. Exporte un CSV **agrégé par émetteur** (totaux nets HT), prêt pour Excel

Un fichier = une facture (ou un avoir) = une ligne dans l’interface. Pas d’historique entre deux lancements : chaque session repart de zéro.

### Formats acceptés

| Format | Exemple | Notes |
|---|---|---|
| PDF texte | facture « sélectionnable » | Extraction directe du texte |
| PDF scanné | photo / scan | OCR automatique (Tesseract) |
| JPG, PNG, HEIC | photo de facture | OCR ; le statut reste « À vérifier » par prudence |

### Installer (macOS)

Téléchargez la dernière version : [GitHub Releases](https://github.com/Ant3xes/pdf-to-csv/releases/latest)

1. Téléchargez le fichier `ConvertisseurFactures-….dmg`
2. Ouvrez le `.dmg` et glissez **Convertisseur Factures** dans **Applications**
3. **Première ouverture** : clic droit → **Ouvrir** → confirmer  
   (macOS bloque les apps non signées au simple double-clic)
4. Ensuite, lancez l’app par double-clic comme n’importe quelle application

### Mettre à jour

1. Téléchargez le nouveau `.dmg` depuis [la dernière release](https://github.com/Ant3xes/pdf-to-csv/releases/latest)
2. Glissez la nouvelle app dans Applications (remplacez l’ancienne)
3. Si macOS bloque à nouveau : clic droit → **Ouvrir** → confirmer (une fois par version)

### Parcours typique

1. **Déposer** vos fichiers (glisser-déposer ou « choisir des fichiers »)
2. Attendre le traitement — chaque document apparaît dans **Documents**, regroupé par émetteur
3. Cliquer sur une ligne pour **apercevoir** le fichier à droite et vérifier les champs
4. Corriger si besoin (émetteur, date, montant HT, type Facture / Avoir) — surtout les lignes **À vérifier**
5. Consulter la **synthèse par émetteur** (totaux nets HT du lot)
6. Cliquer **Exporter CSV** quand toutes les lignes sont OK et ont un émetteur

### Statuts

| Statut | Signification |
|---|---|
| **OK** | Extraction jugée fiable (PDF texte + template connu + champs valides) |
| **À vérifier** | Au moins un doute : fournisseur inconnu, champs manquants/invalides, OCR, ou plusieurs templates possibles |

Tant qu’une ligne est « À vérifier » **ou** sans émetteur, l’export est **bloqué**.

Cas fréquents d’« À vérifier » :

- Fournisseur jamais vu (pas de modèle pour ce layout)
- Document scanné ou image (OCR = toujours à contrôler)
- Date ou montant HT illisible / absents
- Plusieurs fournisseurs possibles pour le même texte (ambiguïté)

### Factures et avoirs

- Une **facture** et un **avoir** suivent le même parcours (1 fichier → 1 ligne).
- Un avoir est reconnu surtout via le titre ou le nom de fichier (« AVOIR », « votre avoir », etc.). En cas de doute, le document reste une facture.
- À l’export, les montants d’avoirs **se déduisent** du total net de l’émetteur (montants négatifs).

### Format du CSV exporté

Séparateur `;` (Excel FR), décimale avec virgule. **Une ligne par émetteur**, pas une ligne par fichier :

```csv
emetteur;montant_ht;nb_documents
Masse;1578,39;3
Aluplast;269,50;1
Hennequin;400,80;2
```

| Colonne | Contenu |
|---|---|
| `emetteur` | Nom de la société qui facture |
| `montant_ht` | Total net HT (factures + avoirs) |
| `nb_documents` | Nombre de fichiers agrégés pour cet émetteur |

Le détail fichier par fichier reste visible dans l’application ; seul le CSV est agrégé.

### Limites (V1)

- Pas d’édition des modèles fournisseurs depuis l’interface (fichiers YAML côté technique)
- Pas de sauvegarde de session / historique
- Les **quittances** de loyer ne sont pas prises en charge (ce ne sont pas des factures fournisseurs)
- App distribuée **non signée** : première ouverture via clic droit → Ouvrir

---

## Pour le développeur

### Principes

- Extraction **100 % déterministe** (pas de LLM) — [ADR-0001](docs/adr/0001-pas-de-llm-pour-extraction.md)
- Interface **Flask + JS** (drag & drop, édition inline, aperçu) — [ADR-0002](docs/adr/0002-interface-flask-js.md)
- Champ montant = **HT uniquement** (pas de dérivation TTC → HT) — [ADR-0003](docs/adr/0003-montant-ht.md)
- Export CSV **agrégé par émetteur** — [ADR-0004](docs/adr/0004-export-agrege-par-emetteur.md)

Vocabulaire du domaine et règles métier : [`CONTEXT.md`](CONTEXT.md). Spec produit élargie : [`PROJET_FACTURES_PDF_TO_CSV.md`](PROJET_FACTURES_PDF_TO_CSV.md).

### Pipeline

```
Fichiers déposés (Lot)
        │
        ▼
Texte natif (pdfplumber) ──insuffisant──► OCR (Tesseract + Poppler / images)
        │                                         │
        └────────────────┬────────────────────────┘
                         ▼
        Détection fournisseur (keywords des templates YAML)
                         │
            un seul match │ ambigu / aucun
                         ▼
        Appliquer template (issuer fixe + regex date / amount HT)
                         │
                         ▼
        Statut OK ou A_VERIFIER → UI éditable → export CSV agrégé
```

### Stack

| Couche | Techno |
|---|---|
| UI desktop | `pywebview` + Flask + JS |
| PDF texte | `pdfplumber` |
| OCR | `pytesseract`, `pdf2image` (Poppler), Tesseract `fra` |
| Images HEIC | `pillow-heif` (+ `libheif` système) |
| Templates | YAML dans `invoice_templates/` (esprit invoice2data) |
| Packaging macOS | PyInstaller → `.app` + `.dmg` |

Modules principaux sous `app/` : `lot.py` (traitement), `web.py` (API Flask), `export_agrege.py` / `csv_export.py`, `launcher.py` (fenêtre native).

### Prérequis système

```bash
brew install tesseract tesseract-lang poppler libheif
```

Vérifier : `tesseract --version`, `pdftoppm -v`, langue `fra` installée.

### Environnement Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Pour le build release : aussi `pip install -r requirements-build.txt`.

### Lancer depuis les sources

```bash
source .venv/bin/activate
python -m app.launcher
```

### Templates fournisseurs

Un fichier YAML par fournisseur récurrent dans `invoice_templates/`. Ajouter un fournisseur = ajouter un fichier, sans toucher au code.

Exemple :

```yaml
issuer: Aluplast
keywords:
  - Aluplast
  - ZA La Prévôté
fields:
  date: 'Date\s*:\s*(\d{2}/\d{2}/\d{2})'
  amount: 'Montant €\s+(\d+[,.]\d{2})\s+\d+[,.]\d{2}\s+\d+[,.]\d{2}\s+\d+[,.]\d{2}'
options:
  date_formats:
    - '%d/%m/%y'
  decimal_separator: ','
```

Règles importantes :

- `issuer` est une **valeur fixe** du template (jamais une regex sur le PDF)
- `amount` cible le **montant HT**, jamais le TTC
- Relation **1:1** fournisseur ↔ template actif
- Si plusieurs templates matchent → détection ambiguë → aucun template appliqué → `A_VERIFIER`

### Corpus de référence

Le dossier [`private_corpus/`](private_corpus/) contient des documents réels pour concevoir les templates et valider le pipeline. Ce n’est **pas** une base applicative.

Smoke tests prioritaires (PDF natifs OK / OCR / sans template) : voir section Tests ci-dessous et le détail dans `PROJET_FACTURES_PDF_TO_CSV.md`.

### Tests

```bash
source .venv/bin/activate
pytest
```

Couverture indicative du parcours Lot → CSV :

- PDF natifs avec template (Masse, Domaine des Jumeaux, Devaud, Aluplast) → `OK`
- PDF sans template (ACR) → `A_VERIFIER`, sans émetteur auto
- PDF scanné (Altagel) → champs éventuels + `A_VERIFIER`
- Images (JPG, PNG, HEIC) → OCR + `A_VERIFIER`

### Build et release macOS

Guide détaillé : [`docs/build-macos-release.md`](docs/build-macos-release.md).

```bash
./scripts/build-release.sh 1.0.0
```

Produit `dist/Convertisseur Factures.app` et `dist/ConvertisseurFactures-1.0.0.dmg`. Signature / notarisation optionnelles (variables `APPLE_*` sur la machine du mainteneur uniquement).

### Structure du dépôt (repères)

```
app/                  # Application (launcher, web, lot, export, static)
invoice_templates/    # YAML par fournisseur
tests/                # pytest (+ Playwright pour l’UI)
private_corpus/     # Corpus de validation
packaging/            # Spec PyInstaller, vendor OCR
scripts/              # build-release, stage-vendor
docs/adr/             # Décisions d’architecture
CONTEXT.md            # Langage ubiquitaire / règles métier
```

### Contribution / agents

Conventions agents et triage issues : [`AGENTS.md`](AGENTS.md) et [`docs/agents/`](docs/agents/).

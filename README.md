# pdf-to-csv

Convertisseur local de factures PDF et images (JPG, PNG, HEIC) vers CSV (extraction déterministe, sans LLM).

## Setup

### Prérequis système

- **Tesseract OCR** (binaire système, pas seulement le wrapper Python) — requis pour les PDF scannés / sans texte natif exploitable et pour les fichiers image.
- **Poppler** (`pdftoppm`) — requis par `pdf2image` pour rasteriser les PDF avant OCR.
- **libheif** (optionnel, recommandé pour HEIC) — requis par `pillow-heif` pour lire les photos iPhone (`.heic`).

macOS (Homebrew) :

```bash
brew install tesseract tesseract-lang poppler libheif
```

Vérifier : `tesseract --version` et `pdftoppm -v`. Le pack de langues doit inclure le français (`fra`).

### Environnement Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancer l'application

### Application macOS (installation et mise à jour)

Téléchargez la dernière version depuis [GitHub Releases](https://github.com/Ant3xes/pdf-to-csv/releases/latest) :

1. Ouvrez le fichier `.dmg`
2. Glissez **Convertisseur Factures** dans le dossier Applications
3. Double-cliquez pour lancer l'application

**Mise à jour** : même procédure — remplacez l'ancienne version par la nouvelle.

### Développement (terminal)

Avec les prérequis système installés :

```bash
source .venv/bin/activate
python -m app.launcher
```

Pour builder un `.dmg` de release, voir [docs/build-macos-release.md](docs/build-macos-release.md).

## Tests

```bash
pytest
```

Le parcours Lot → CSV est couvert par les smoke tests du corpus `private_corpus/` :

- PDF natifs : Masse, Domaine des Jumeaux, Devaud, Aluplast → `OK`
- PDF sans template : ACR → `A_VERIFIER`, sans émetteur automatique
- PDF scanné (OCR) : Altagel → champs extraits + statut `A_VERIFIER`
- Images (JPG, PNG, HEIC) : OCR → champs extraits si template/filet applicable + statut `A_VERIFIER`

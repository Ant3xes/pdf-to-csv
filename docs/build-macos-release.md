# Build et publication macOS

Guide mainteneur pour produire un `.dmg` **Convertisseur Factures** et le publier sur GitHub Releases.

## Prérequis

- macOS avec Xcode Command Line Tools (`xcode-select --install`)
- Compte [Apple Developer](https://developer.apple.com) (99 €/an) pour signature et notarisation
- Homebrew avec Tesseract, Poppler et la langue française :

```bash
brew install tesseract tesseract-lang poppler libheif
```

- Certificat **Developer ID Application** installé dans le Trousseau
- Profil notarytool configuré localement (jamais commité) :

```bash
xcrun notarytool store-credentials "pdf-to-csv-notarize" \
  --apple-id "votre@email.com" \
  --team-id "VOTRE_TEAM_ID" \
  --password "mot-de-passe-app-specifique"
```

## Variables d'environnement (locales)

| Variable | Rôle |
|---|---|
| `APPLE_SIGNING_IDENTITY` | Nom du certificat Developer ID, ex. `Developer ID Application: …` |
| `APPLE_NOTARIZE_KEYCHAIN_PROFILE` | Profil notarytool, ex. `pdf-to-csv-notarize` |
| `VERSION` | Version sémantique, ex. `1.0.0` (sans préfixe `v`) |

Ces valeurs restent sur la machine du mainteneur — ne jamais les committer.

## Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-build.txt

export APPLE_SIGNING_IDENTITY="Developer ID Application: …"
export APPLE_NOTARIZE_KEYCHAIN_PROFILE="pdf-to-csv-notarize"

./scripts/build-release.sh 1.0.0
```

Le script :

1. Prépare `packaging/vendor/` (Tesseract, Poppler, tessdata `fra`)
2. Lance PyInstaller → `dist/Convertisseur Factures.app`
3. Signe et notarise (si variables définies)
4. Produit `dist/ConvertisseurFactures-1.0.0.dmg`

Sans variables de signature, le build produit quand même l'application — utile en dev, mais Gatekeeper bloquera chez l'utilisateur final.

## Publication GitHub Releases

```bash
git tag v1.0.0
git push origin v1.0.0

gh release create v1.0.0 \
  dist/ConvertisseurFactures-1.0.0.dmg \
  --title "v1.0.0" \
  --notes "Première version de l'application macOS."
```

Lien permanent pour l'utilisateur :

```
https://github.com/Ant3xes/pdf-to-csv/releases/latest
```

## QA manuelle avant release

Sur une machine non développeur (ou compte standard) :

1. Télécharger le `.dmg` depuis la release
2. Glisser **Convertisseur Factures** dans Applications
3. Double-clic — pas d'avertissement Gatekeeper bloquant
4. Déposer un lot de **Factures** (PDF natif + scanné + image)
5. Corriger une ligne « À vérifier » si nécessaire
6. Exporter le CSV et l'ouvrir dans Excel
7. Fermer la fenêtre — le processus doit quitter proprement

## Lancement depuis le code source (développement)

```bash
source .venv/bin/activate
python -m app.launcher
```

Nécessite les prérequis système Homebrew (voir README).

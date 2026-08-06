# Build et publication macOS

Guide mainteneur pour produire un `.dmg` **Convertisseur Factures** et le publier sur GitHub Releases.

## Prérequis

- macOS avec Xcode Command Line Tools (`xcode-select --install`)
- Homebrew avec Tesseract, Poppler et la langue française :

```bash
brew install tesseract tesseract-lang poppler libheif
```

**Pas de compte Apple Developer requis** : la release est distribuée **non signée**. L'utilisateur final contourne Gatekeeper une fois (clic droit → Ouvrir). La signature / notarisation restent optionnelles si un certificat Developer ID est un jour disponible.

## Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-build.txt

./scripts/build-release.sh 1.0.0
```

Le script :

1. Prépare `packaging/vendor/` (Tesseract, Poppler, tessdata `fra`)
2. Lance PyInstaller → `dist/Convertisseur Factures.app`
3. Produit `dist/ConvertisseurFactures-1.0.0.dmg`

Variable optionnelle : `VERSION` (sinon passer la version en argument).

## Signature / notarisation (optionnel)

Si un certificat Developer ID est disponible plus tard :

| Variable | Rôle |
|---|---|
| `APPLE_SIGNING_IDENTITY` | Nom du certificat, ex. `Developer ID Application: …` |
| `APPLE_NOTARIZE_KEYCHAIN_PROFILE` | Profil notarytool local |

Ces valeurs restent sur la machine du mainteneur — ne jamais les committer. Sans elles, le build ignore signature et notarisation.

## Publication GitHub Releases

```bash
git tag v1.0.0
git push origin v1.0.0

gh release create v1.0.0 \
  dist/ConvertisseurFactures-1.0.0.dmg \
  --title "v1.0.0" \
  --notes "Première version de l'application macOS (non signée)."
```

Lien permanent pour l'utilisateur :

```
https://github.com/Ant3xes/pdf-to-csv/releases/latest
```

## QA manuelle avant release

Sur une machine non développeur (ou compte standard) :

1. Télécharger le `.dmg` depuis la release
2. Glisser **Convertisseur Factures** dans Applications
3. **Première ouverture** : clic droit → Ouvrir → confirmer (Gatekeeper, app non signée)
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

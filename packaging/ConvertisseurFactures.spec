# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# SPECPATH = dossier packaging/ ; la racine du repo est le parent.
# onedir + BUNDLE → .app macOS ; vendor OCR embarqué via datas « vendor/ ».
ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "app" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "invoice_templates"), "invoice_templates"),
        (str(ROOT / "app" / "templates"), "app/templates"),
        (str(ROOT / "app" / "static"), "app/static"),
        (str(ROOT / "packaging" / "vendor"), "vendor"),
    ],
    hiddenimports=[
        "PIL._tkinter_finder",
        "pillow_heif",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Convertisseur Factures",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Convertisseur Factures",
)

app = BUNDLE(
    coll,
    name="Convertisseur Factures.app",
    icon=None,
    bundle_identifier="fr.pdf-to-csv.convertisseur-factures",
)

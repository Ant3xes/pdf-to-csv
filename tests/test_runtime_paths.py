from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from app.lot import process_lot
from app.runtime_paths import RuntimePaths, configure_runtime_paths, resolve_runtime_paths
from tests.helpers import montant_fr

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEMPLATES = Path(__file__).resolve().parents[1] / "invoice_templates"


@pytest.fixture(autouse=True)
def _reset_runtime_paths():
    from app.runtime_paths import reset_runtime_paths

    reset_runtime_paths()
    yield
    reset_runtime_paths()


def _system_tessdata_prefix(tesseract_cmd: str) -> str | None:
    candidates = [
        Path("/opt/homebrew/share"),
        Path(tesseract_cmd).resolve().parent.parent / "share",
    ]
    for candidate in candidates:
        if (candidate / "tessdata" / "fra.traineddata").is_file():
            return str(candidate / "tessdata")
        if (candidate / "fra.traineddata").is_file():
            return str(candidate)
    return None


def _write_bundle_layout(root: Path) -> None:
    bin_dir = root / "vendor" / "bin"
    tessdata_dir = root / "vendor" / "tessdata"
    bin_dir.mkdir(parents=True)
    tessdata_dir.mkdir(parents=True)
    (bin_dir / "tesseract").touch()
    (bin_dir / "pdftoppm").touch()
    (tessdata_dir / "fra.traineddata").touch()


def test_resolve_dev_mode_delegates_to_system_path():
    paths = resolve_runtime_paths(bundle_root=None, packaged=False)

    assert paths.tesseract_cmd is None
    assert paths.poppler_path is None
    assert paths.tessdata_prefix is None


def test_resolve_packaged_layout_with_simulated_bundle(tmp_path: Path):
    _write_bundle_layout(tmp_path)

    paths = resolve_runtime_paths(bundle_root=tmp_path, packaged=True)

    assert paths.tesseract_cmd == str(tmp_path / "vendor" / "bin" / "tesseract")
    assert paths.poppler_path == str(tmp_path / "vendor" / "bin")
    assert paths.tessdata_prefix == str(tmp_path / "vendor" / "tessdata")


def test_configure_runtime_paths_applies_tesseract_and_tessdata(tmp_path: Path):
    _write_bundle_layout(tmp_path)
    paths = resolve_runtime_paths(bundle_root=tmp_path, packaged=True)

    configure_runtime_paths(paths)

    import pytesseract

    assert pytesseract.pytesseract.tesseract_cmd == paths.tesseract_cmd
    assert os.environ["TESSDATA_PREFIX"] == paths.tessdata_prefix


@pytest.mark.skipif(
    shutil.which("tesseract") is None or shutil.which("pdftoppm") is None,
    reason="Tesseract et Poppler requis pour le test d'intégration OCR",
)
def test_process_lot_ocr_with_configured_runtime_paths():
    tesseract = shutil.which("tesseract")
    pdftoppm = shutil.which("pdftoppm")
    assert tesseract is not None and pdftoppm is not None

    prefix = _system_tessdata_prefix(tesseract)
    assert prefix is not None, "tessdata fra introuvable sur le système"

    configure_runtime_paths(
        RuntimePaths(
            tesseract_cmd=tesseract,
            poppler_path=str(Path(pdftoppm).parent),
            tessdata_prefix=prefix,
        )
    )

    lignes = process_lot([FIXTURES / "scan_sans_texte.pdf"], TEMPLATES)

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne.fichier == "scan_sans_texte.pdf"
    assert ligne.emetteur == "Altagel"
    assert ligne.date == "15/03/2026"
    assert montant_fr(ligne) == "99,50"
    assert ligne.statut == "A_VERIFIER"

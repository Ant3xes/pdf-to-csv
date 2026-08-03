# pdf-to-csv

Convertisseur local de factures PDF vers CSV (extraction déterministe, sans LLM).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tests

```bash
pytest
```

Le parcours Lot → CSV pour les PDF natifs du corpus `private_corpus/` est couvert par les smoke tests (Masse, Domaine des Jumeaux, Devaud, Aluplast).

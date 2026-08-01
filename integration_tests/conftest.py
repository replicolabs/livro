import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for pkg_root in ("tax_engine", "ledger", "trust", "rendering"):
    sys.path.insert(0, str(ROOT / pkg_root))

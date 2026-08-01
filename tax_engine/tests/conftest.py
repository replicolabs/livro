import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_engine.tables import load_table  # noqa: E402


@pytest.fixture
def carne_leao_table():
    return load_table("carne_leao_2026.json")


@pytest.fixture
def capital_gains_table():
    return load_table("capital_gains_2026.json")


@pytest.fixture
def in1888_table():
    return load_table("in1888_threshold_2026.json")

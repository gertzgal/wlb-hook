import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def fixture():
    def load(event: str, name: str) -> dict:
        return json.loads((FIXTURES / event / f"{name}.json").read_text())
    return load

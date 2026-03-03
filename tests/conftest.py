import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_sessionstart() -> None:
    os.environ.setdefault("ES_URL", "http://localhost:9200")
    os.environ.setdefault("ES_API_KEY", "dummy-api-key")
    os.environ.setdefault("ES_SPACE", "default")
    os.environ.setdefault("EQTR_AUTH_BEARER_TOKEN", "secret-token")

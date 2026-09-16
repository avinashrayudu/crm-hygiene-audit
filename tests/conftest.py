import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pytest_sessionstart(session):
    """Generate the fake sample data once if it isn't there yet."""
    if not any((ROOT / "data").glob("*.csv")):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_sample_data.py")], check=True)

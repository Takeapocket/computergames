"""Source and frozen executable entry for the separate Qt preview."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_qt.app import main

if __name__ == "__main__":
    raise SystemExit(main())

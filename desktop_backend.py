"""Repository-local launcher for the Flutter desktop bridge."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from engine_doc.desktop_api import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

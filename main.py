"""Repository-local launcher; installation is optional."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from engine_doc.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())


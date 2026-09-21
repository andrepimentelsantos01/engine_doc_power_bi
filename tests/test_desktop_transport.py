from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine_doc.desktop_service import DesktopService


class DesktopTransportTests(unittest.TestCase):
    fixtures = ROOT / "tests" / "fixtures"

    def test_compact_analysis_returns_path_without_large_text_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = DesktopService(Path(temp_dir) / "output").analyze_project(
                str(self.fixtures), include_content=False
            )

            self.assertNotIn("content", result)
            xray = Path(result["xray_path"])
            self.assertTrue(xray.is_file())
            self.assertIn("RAIO-X DO PROJETO", xray.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

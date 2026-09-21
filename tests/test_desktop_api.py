from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine_doc.ai import NVIDIA_MODEL, OPENROUTER_MODEL, OpenRouterModel
from engine_doc.desktop_api import create_server
from engine_doc.desktop_service import DesktopService, DesktopServiceError


class DesktopServiceTests(unittest.TestCase):
    fixtures = ROOT / "tests" / "fixtures"

    def test_analyzes_selected_pbip_with_existing_core(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DesktopService(Path(temp_dir) / "output")

            result = service.analyze_project(str(self.fixtures.resolve()))

            self.assertTrue(result["success"])
            self.assertEqual("Sales", result["project_name"])
            self.assertIn("RAIO-X DO PROJETO", result["content"])
            self.assertTrue(Path(result["xray_path"]).is_file())

    def test_rejects_missing_and_incompatible_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = DesktopService(root / "output")
            with self.assertRaisesRegex(DesktopServiceError, "não existe"):
                service.analyze_project(str(root / "missing"))
            with self.assertRaisesRegex(DesktopServiceError, "PBIP compatível"):
                service.analyze_project(str(root))

    @patch("engine_doc.desktop_service.list_free_models")
    def test_openrouter_models_come_from_existing_python_logic(self, list_models) -> None:
        list_models.return_value = [
            OpenRouterModel(OPENROUTER_MODEL, "Automático", 131072),
            OpenRouterModel("provider/free", "Modelo gratuito", 65536),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            result = DesktopService(Path(temp_dir)).list_openrouter_models("segredo")

        self.assertEqual(OPENROUTER_MODEL, result["models"][0]["id"])
        self.assertTrue(result["models"][0]["automatic"])
        list_models.assert_called_once_with("segredo")

    @patch("engine_doc.desktop_service.review_ray_x")
    def test_generates_critical_analysis_with_existing_reviewer(self, review) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output"
            project_dir = output / "Sales"
            project_dir.mkdir(parents=True)
            xray = project_dir / "Sales_raio_x.txt"
            xray.write_text("raio-x", encoding="utf-8")
            destination = project_dir / "Sales_raio_x_analise_ia.txt"

            def fake_review(path: Path, key: str, **options: object) -> Path:
                self.assertEqual("segredo", key)
                self.assertEqual("NVIDIA NIM", options["provider"])
                self.assertEqual(NVIDIA_MODEL, options["model"])
                destination.write_text("análise pronta", encoding="utf-8")
                return destination

            review.side_effect = fake_review
            result = DesktopService(output).generate_ai(
                mode="critical_analysis",
                provider="nvidia",
                api_key="segredo",
                xray_path_value=str(xray),
            )

            self.assertEqual("análise pronta", result["content"])
            self.assertEqual("critical_analysis", result["type"])

    def test_api_key_is_redacted_from_controlled_errors(self) -> None:
        secret = "sk-test-secret-value"
        error = DesktopService._ai_error(
            RuntimeError(f"falha interna {secret}"), secret
        )
        self.assertNotIn(secret, error.message)
        self.assertEqual("provider_error", error.code)

    def test_refuses_to_read_xray_outside_managed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside_raio_x.txt"
            outside.write_text("privado", encoding="utf-8")
            service = DesktopService(root / "output")
            with self.assertRaisesRegex(DesktopServiceError, "não pertence"):
                service.existing_results(str(outside))


class DesktopApiServerTests(unittest.TestCase):
    def test_server_is_bound_only_to_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = create_server(Path(temp_dir), port=0)
            try:
                self.assertEqual("127.0.0.1", server.server_address[0])
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()

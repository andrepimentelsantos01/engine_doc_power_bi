from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine_doc.analysis.dependencies import analyze_dependencies
from engine_doc.cli import _relative_output_paths, analyze
from engine_doc.discovery import discover_projects
from engine_doc.models import PBIPProject
from engine_doc.parsers import parse_report, parse_semantic_model


class EngineDocTests(unittest.TestCase):
    fixtures = ROOT / "tests" / "fixtures"

    def test_discovers_descriptor_and_artifacts(self) -> None:
        projects = discover_projects(self.fixtures)
        self.assertEqual(1, len(projects))
        self.assertEqual("Sales", projects[0].name)
        self.assertEqual("Sales.SemanticModel", projects[0].semantic_model_path.name)
        self.assertEqual("Sales.Report", projects[0].report_path.name)

    def test_parses_tmdl_inventory(self) -> None:
        model = parse_semantic_model(self.fixtures / "Sales.SemanticModel")
        self.assertEqual(1600, model.compatibility_level)
        self.assertEqual("en-US", model.culture)
        self.assertEqual(2, len(model.tables))
        sales = next(table for table in model.tables if table.name == "Sales")
        self.assertEqual(3, len(sales.columns))
        self.assertEqual(2, len(sales.measures))
        self.assertTrue(next(c for c in sales.columns if c.name == "Amount With Tax").calculated)
        self.assertIn("DIVIDE", next(m for m in sales.measures if m.name == "Sales Share").expression)
        self.assertEqual(1, len(model.relationships))

    def test_extracts_dependencies(self) -> None:
        model = parse_semantic_model(self.fixtures / "Sales.SemanticModel")
        dependencies = analyze_dependencies(model)
        triples = {(item.source, item.target, item.kind) for item in dependencies}
        self.assertIn(
            ("measure:Sales[Total Sales]", "column:Sales[Amount]", "column_reference"),
            triples,
        )
        self.assertIn(
            ("measure:Sales[Sales Share]", "measure:Sales[Total Sales]", "measure_reference"),
            triples,
        )
        self.assertIn(
            ("column:Sales[ProductId]", "column:Product[ProductId]", "relationship"),
            triples,
        )

    def test_parses_report(self) -> None:
        report = parse_report(self.fixtures / "Sales.Report")
        self.assertEqual(1, len(report.pages))
        self.assertEqual("Executive Overview", report.pages[0].display_name)
        self.assertEqual(["clusteredColumnChart"], report.pages[0].visual_types)

    def test_generates_documentation_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            count = analyze(self.fixtures, output)
            self.assertEqual(1, count)
            project_output = output / "Sales"
            self.assertTrue((output / "index.html").exists())
            self.assertTrue((project_output / "README.md").exists())
            self.assertTrue((project_output / "lineage.mmd").exists())
            ray_x = project_output / "Sales_raio_x.txt"
            self.assertTrue(ray_x.exists())
            ray_x_text = ray_x.read_text(encoding="utf-8")
            self.assertIn("RAIO-X TÉCNICO DO PROJETO", ray_x_text)
            self.assertIn("MEDIDAS", ray_x_text)
            self.assertIn("Total Sales", ray_x_text)
            metadata = json.loads((project_output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual("Sales", metadata["name"])
            self.assertEqual(2, len(metadata["model"]["tables"]))

    def test_mirrors_multiple_input_folders_without_name_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            shutil.copytree(self.fixtures, input_dir / "projeto1")
            shutil.copytree(self.fixtures, input_dir / "projeto2")

            count = analyze(input_dir, output_dir)

            self.assertEqual(2, count)
            first = output_dir / "projeto1" / "Sales_raio_x.txt"
            second = output_dir / "projeto2" / "Sales_raio_x.txt"
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertIn("Projeto: Sales", first.read_text(encoding="utf-8"))
            self.assertIn("Projeto: Sales", second.read_text(encoding="utf-8"))
            self.assertFalse((output_dir / "Sales").exists())

    def test_disambiguates_multiple_descriptors_in_same_container(self) -> None:
        input_dir = Path("input").resolve()
        shared_root = input_dir / "cliente"
        projects = [
            PBIPProject(name="Financeiro", root=shared_root),
            PBIPProject(name="Comercial", root=shared_root),
        ]
        self.assertEqual(
            [Path("cliente/Financeiro"), Path("cliente/Comercial")],
            _relative_output_paths(projects, input_dir),
        )

    def test_normalized_names_can_never_overwrite_each_other(self) -> None:
        input_dir = Path("input").resolve()
        shared_root = input_dir / "cliente"
        projects = [
            PBIPProject(name="Modelo A", root=shared_root),
            PBIPProject(name="Modelo_A", root=shared_root),
        ]
        self.assertEqual(
            [Path("cliente/Modelo_A"), Path("cliente/Modelo_A_2")],
            _relative_output_paths(projects, input_dir),
        )


if __name__ == "__main__":
    unittest.main()

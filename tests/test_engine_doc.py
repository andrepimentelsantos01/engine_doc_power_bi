from __future__ import annotations

import json
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine_doc.analysis.dependencies import analyze_dependencies
from engine_doc.analysis.report_usage import (
    analyze_report_dependencies,
    collect_report_usage,
    downstream_dependencies,
)
from engine_doc.cli import _relative_output_paths, analyze, main
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
        self.assertIn(
            ("measure:Sales[Total Sales]", "table:Sales", "measure_member_of"),
            triples,
        )
        self.assertIn(
            ("column:Product[Name]", "table:Product", "column_member_of"),
            triples,
        )
        self.assertIn(
            ("table:Sales", "source:Sales/Sales", "table_loaded_from_partition"),
            triples,
        )

    def test_parses_report(self) -> None:
        report = parse_report(self.fixtures / "Sales.Report")
        self.assertEqual(2, len(report.pages))
        self.assertEqual("Engine Doc Test Theme", report.theme)
        self.assertEqual("Amount", report.filters[0].fields[0].name)
        self.assertEqual("Executive Overview", report.pages[0].display_name)
        self.assertEqual(3, report.pages[0].visual_count)
        self.assertIn("clusteredColumnChart", report.pages[0].visual_types)
        chart = next(visual for visual in report.pages[0].visuals if visual.name == "Visual1")
        self.assertEqual("Sales by Product", chart.title)
        self.assertEqual({"measure", "column"}, {field.kind for field in chart.fields})
        self.assertEqual("Sales", next(f for f in chart.fields if f.kind == "measure").table)
        self.assertEqual("Amount", chart.filters[0].fields[0].name)
        self.assertEqual("ProductId", report.pages[0].filters[0].fields[0].name)
        table_visual = report.pages[1].visuals[0]
        aggregate = next(field for field in table_visual.fields if field.aggregation)
        self.assertEqual("sum", aggregate.aggregation)
        unresolved = next(field for field in table_visual.fields if field.name == "Missing Field")
        self.assertEqual("reference", unresolved.resolution)
        empty_visual = next(
            visual for visual in report.pages[0].visuals if visual.name == "VisualEmpty"
        )
        self.assertEqual([], empty_visual.fields)

    def test_report_usage_dependencies_and_impact(self) -> None:
        project = PBIPProject(name="Sales", root=self.fixtures)
        project.model = parse_semantic_model(self.fixtures / "Sales.SemanticModel")
        project.report = parse_report(self.fixtures / "Sales.Report")
        project.dependencies = analyze_dependencies(project.model)
        project.dependencies.extend(analyze_report_dependencies(project))

        triples = {(item.source, item.target, item.kind) for item in project.dependencies}
        self.assertIn(
            ("visual:Page1/Visual1", "measure:Sales[Total Sales]", "visual_measure_explicit"),
            triples,
        )
        self.assertIn(
            ("page:Page1", "visual:Page1/Visual1", "page_contains_visual"),
            triples,
        )
        self.assertTrue(any("undetermined" in kind for _, _, kind in triples))

        usage = collect_report_usage(project)
        measure_usage = usage["measure:Sales[Total Sales]"]
        self.assertEqual(3, len(measure_usage))
        self.assertEqual({"Page1", "Page2"}, {item.page_name for item in measure_usage})
        impact = downstream_dependencies(project, "column:Sales[Amount]")
        self.assertIn("measure:Sales[Total Sales]", impact)
        self.assertIn("visual:Page1/Visual1", impact)
        self.assertIn("page:Page1", impact)

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
            self.assertIn("RAIO-X DO PROJETO", ray_x_text)
            self.assertIn("FONTES", ray_x_text)
            self.assertIn("MEDIDA: Sales[Total Sales]", ray_x_text)
            self.assertIn("Total Sales", ray_x_text)
            self.assertIn("PÁGINAS E VISUAIS", ray_x_text)
            self.assertIn("Sales by Product", ray_x_text)
            self.assertIn("LINEAGE", ray_x_text)
            self.assertIn("ANÁLISE DE IMPACTO", ray_x_text)
            self.assertIn("AVISOS", ray_x_text)
            self.assertIn("Dependência não determinada", ray_x_text)
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

    def test_empty_input_returns_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stream = io.StringIO()
            with redirect_stdout(stream):
                result = main(
                    [
                        "--input",
                        str(root / "input"),
                        "--output",
                        str(root / "output"),
                        "--skip-ai",
                    ]
                )
            self.assertEqual(1, result)
            self.assertIn("Nenhum projeto PBIP foi encontrado", stream.getvalue())
            self.assertIn("Coloque um projeto PBIP", stream.getvalue())

    def test_invalid_visual_is_localized_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_root = Path(temp_dir) / "Sales.Report"
            shutil.copytree(self.fixtures / "Sales.Report", report_root)
            invalid_visual = (
                report_root
                / "definition"
                / "pages"
                / "Page1"
                / "visuals"
                / "Visual1"
                / "visual.json"
            )
            invalid_visual.write_text("{json inválido", encoding="utf-8")
            warnings: list[str] = []

            report = parse_report(report_root, warnings=warnings)

            self.assertEqual(2, len(report.pages))
            self.assertTrue(any("Visual Visual1" in warning for warning in warnings))
            self.assertTrue(any(page.visuals for page in report.pages))

    def test_example_project_is_analyzable(self) -> None:
        example_root = ROOT / "examples" / "projetodashBI"
        projects = discover_projects(example_root)
        self.assertEqual(1, len(projects))
        project = projects[0]
        model = parse_semantic_model(project.semantic_model_path)
        report = parse_report(project.report_path)
        self.assertEqual(3, len(model.tables))
        self.assertEqual(5, len(report.pages))
        self.assertGreater(sum(page.visual_count for page in report.pages), 0)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine_doc.ai.nvidia_client import (
    NVIDIA_ENDPOINT,
    NVIDIA_MAX_TOKENS,
    NVIDIA_MODEL,
    NVIDIA_REASONING_BUDGET,
    NvidiaClientError,
    request_review,
)
from engine_doc.ai.openrouter_client import (
    OPENROUTER_ENDPOINT,
    OPENROUTER_MODEL,
    OpenRouterClientError,
    list_free_models,
    request_review as request_openrouter_review,
)
from engine_doc.ai.reviewer import ReviewOutputError, analysis_path, review_ray_x
from engine_doc.cli import run_ai_reviews
from engine_doc.models import PBIPProject


VALID_ANALYSIS = """VISÃO GERAL
O projeto apresenta um modelo semântico pequeno e organizado. A leitura foi
realizada somente a partir das informações disponíveis no raio-X técnico.

PONTOS POSITIVOS
As tabelas e medidas estão documentadas e possuem dependências identificadas.
Os relacionamentos encontrados seguem a estrutura descrita pelos metadados.

PONTOS QUE MERECEM ATENÇÃO
Objetos sem consumo final devem ser revisados com o responsável pelo projeto.
A ausência de uso direto não constitui autorização para removê-los.

PERFORMANCE
Não existem métricas de execução suficientes para afirmar que o projeto está
lento. Padrões potencialmente caros devem ser medidos antes de qualquer mudança.

RELACIONAMENTOS
Não há evidência suficiente para recomendar mudança na direção dos filtros.

RELATÓRIO
As páginas, os visuais e seus campos foram considerados na análise técnica.

DEPENDÊNCIAS E IMPACTO
As cadeias apresentadas são baseadas somente nas dependências comprovadas.

PRIORIDADES SUGERIDAS
REVISAR os objetos sem consumo identificado antes de decidir qualquer remoção.

CONCLUSÃO
O projeto deve ser validado no Power BI antes de receber alterações estruturais.
Recomendação produzida com base exclusiva no raio-X fornecido."""


class NvidiaClientTests(unittest.TestCase):
    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_calls_endpoint_with_headers_payload_and_extracts_text(self, post: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "  análise técnica  "}}]
        }
        post.return_value = response

        result = request_review("chave-secreta", "instruções", "conteúdo do raio-x")

        self.assertEqual("análise técnica", result)
        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual(NVIDIA_ENDPOINT, post.call_args.args[0])
        self.assertEqual("Bearer chave-secreta", kwargs["headers"]["Authorization"])
        self.assertEqual("application/json", kwargs["headers"]["Accept"])
        self.assertFalse(kwargs["stream"])
        self.assertEqual(NVIDIA_MODEL, kwargs["json"]["model"])
        self.assertEqual(NVIDIA_MAX_TOKENS, kwargs["json"]["max_tokens"])
        self.assertEqual(NVIDIA_REASONING_BUDGET, kwargs["json"]["reasoning_budget"])
        self.assertNotIn("prompt", kwargs["json"])
        self.assertEqual("instruções", kwargs["json"]["messages"][0]["content"])
        self.assertEqual("conteúdo do raio-x", kwargs["json"]["messages"][1]["content"])
        self.assertNotIn("chave-secreta", str(kwargs["json"]))

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_empty_key_never_calls_nvidia(self, post: Mock) -> None:
        with self.assertRaisesRegex(NvidiaClientError, "não foi informada"):
            request_review("", "system", "ray-x")
        post.assert_not_called()

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_authentication_errors_are_controlled(self, post: Mock) -> None:
        for status in (401, 403):
            with self.subTest(status=status):
                post.return_value = Mock(status_code=status)
                with self.assertRaisesRegex(NvidiaClientError, "autenticar"):
                    request_review("segredo", "system", "ray-x")

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_rate_limit_is_controlled(self, post: Mock) -> None:
        post.return_value = Mock(status_code=429)
        with self.assertRaisesRegex(NvidiaClientError, "Limite de requisições"):
            request_review("segredo", "system", "ray-x")

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_validation_error_is_useful_and_redacts_key(self, post: Mock) -> None:
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": {"message": "Invalid field; token recebido: segredo-real"}
        }
        post.return_value = response
        with self.assertRaises(NvidiaClientError) as context:
            request_review("segredo-real", "system", "ray-x")
        message = str(context.exception)
        self.assertIn("Invalid field", message)
        self.assertNotIn("segredo-real", message)
        self.assertIn("credencial removida", message)

    @patch("engine_doc.ai.nvidia_client.requests.post", side_effect=requests.Timeout)
    def test_timeout_is_controlled(self, post: Mock) -> None:
        with self.assertRaisesRegex(NvidiaClientError, "demorou mais"):
            request_review("segredo", "system", "ray-x")

    @patch("engine_doc.ai.nvidia_client.requests.post", side_effect=requests.ConnectionError)
    def test_connection_failure_is_controlled(self, post: Mock) -> None:
        with self.assertRaisesRegex(NvidiaClientError, "conectar"):
            request_review("segredo", "system", "ray-x")

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_invalid_json_is_controlled(self, post: Mock) -> None:
        response = Mock(status_code=200)
        response.json.side_effect = ValueError
        post.return_value = response
        with self.assertRaisesRegex(NvidiaClientError, "não pôde ser interpretada"):
            request_review("segredo", "system", "ray-x")

    @patch("engine_doc.ai.nvidia_client.requests.post")
    def test_unexpected_json_is_controlled(self, post: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"unexpected": True}
        post.return_value = response
        with self.assertRaisesRegex(NvidiaClientError, "não pôde ser interpretada"):
            request_review("segredo", "system", "ray-x")


class ReviewerTests(unittest.TestCase):
    def test_reads_entire_xray_and_writes_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ray_x = Path(temp_dir) / "modelo_raio_x.txt"
            original = "RAIO-X COMPLETO\nMedida: Receita"
            ray_x.write_text(original, encoding="utf-8")
            captured: dict[str, str] = {}

            def client(api_key: str, system: str, user: str) -> str:
                captured.update(api_key=api_key, system=system, user=user)
                return VALID_ANALYSIS

            generated = review_ray_x(ray_x, "segredo", client=client)

            self.assertEqual(original, ray_x.read_text(encoding="utf-8"))
            self.assertIn(original, captured["user"])
            self.assertIn("Analise SOMENTE", captured["system"])
            result = generated.read_text(encoding="utf-8")
            self.assertIn(NVIDIA_MODEL, result)
            self.assertIn("Recomendação produzida", result)
            self.assertNotIn("segredo", result)
            self.assertNotIn("segredo", ray_x.read_text(encoding="utf-8"))

    def test_failure_preserves_xray_and_does_not_create_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ray_x = Path(temp_dir) / "modelo_raio_x.txt"
            original = "conteúdo determinístico"
            ray_x.write_text(original, encoding="utf-8")

            def failing_client(api_key: str, system: str, user: str) -> str:
                raise NvidiaClientError("falha controlada")

            with self.assertRaises(NvidiaClientError):
                review_ray_x(ray_x, "segredo", client=failing_client)
            self.assertEqual(original, ray_x.read_text(encoding="utf-8"))
            self.assertFalse(analysis_path(ray_x).exists())

    def test_invalid_provider_output_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ray_x = Path(temp_dir) / "modelo_raio_x.txt"
            ray_x.write_text("raio-x válido", encoding="utf-8")

            with self.assertRaisesRegex(ReviewOutputError, "resposta incompleta"):
                review_ray_x(
                    ray_x,
                    "segredo",
                    client=lambda *_: "All articles reviewed <unk><unk>",
                )

            self.assertFalse(analysis_path(ray_x).exists())

    def test_cli_requests_key_only_after_xray_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            project = PBIPProject(name="Projeto", root=target)
            ray_x = target / "Projeto_raio_x.txt"
            ray_x.write_text("raio-x pronto", encoding="utf-8")
            events: list[str] = []

            def key_reader(prompt: str) -> str:
                self.assertTrue(ray_x.is_file())
                events.append("key")
                return "segredo"

            def fake_review(path: Path, key: str, **options: object) -> Path:
                events.append("review")
                destination = analysis_path(path)
                destination.write_text("análise", encoding="utf-8")
                return destination

            with patch("engine_doc.cli.review_ray_x", side_effect=fake_review):
                generated = run_ai_reviews(
                    [(project, target)],
                    key_reader=key_reader,
                    input_reader=lambda _: "1",
                )
            self.assertEqual(["key", "review"], events)
            self.assertEqual([analysis_path(ray_x)], generated)

    def test_empty_key_skips_review_and_preserves_xray(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            project = PBIPProject(name="Projeto", root=target)
            ray_x = target / "Projeto_raio_x.txt"
            ray_x.write_text("raio-x pronto", encoding="utf-8")
            with patch("engine_doc.cli.review_ray_x") as review:
                generated = run_ai_reviews(
                    [(project, target)],
                    key_reader=lambda _: "",
                    input_reader=lambda _: "1",
                )
            self.assertEqual([], generated)
            review.assert_not_called()
            self.assertEqual("raio-x pronto", ray_x.read_text(encoding="utf-8"))

    def test_no_ai_never_requests_a_key_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            project = PBIPProject(name="Projeto", root=target)
            ray_x = target / "Projeto_raio_x.txt"
            ray_x.write_text("raio-x pronto", encoding="utf-8")
            key_reader = Mock()
            with patch("engine_doc.cli.review_ray_x") as review:
                generated = run_ai_reviews(
                    [(project, target)],
                    key_reader=key_reader,
                    input_reader=lambda _: "0",
                )
            self.assertEqual([], generated)
            key_reader.assert_not_called()
            review.assert_not_called()


class OpenRouterClientTests(unittest.TestCase):
    @staticmethod
    def _model(model_id: str, prompt: str, completion: str) -> dict:
        return {
            "id": model_id,
            "name": model_id,
            "context_length": 131072,
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "pricing": {
                "prompt": prompt,
                "completion": completion,
                "request": "0",
            },
        }

    @patch("engine_doc.ai.openrouter_client.requests.get")
    def test_catalog_exposes_only_confirmed_free_text_models(self, get: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [
                self._model(OPENROUTER_MODEL, "0", "0"),
                self._model("provider/free-model", "0", "0"),
                self._model("provider/paid-model", "0.0001", "0"),
            ]
        }
        get.return_value = response

        models = list_free_models("segredo")

        self.assertEqual(
            {OPENROUTER_MODEL, "provider/free-model"},
            {model.id for model in models},
        )

    @patch("engine_doc.ai.openrouter_client.requests.post")
    @patch("engine_doc.ai.openrouter_client.requests.get")
    def test_paid_or_unconfirmed_model_never_reaches_post(
        self, get: Mock, post: Mock
    ) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [self._model(OPENROUTER_MODEL, "0", "0")]
        }
        get.return_value = response

        with self.assertRaisesRegex(OpenRouterClientError, "confirmar"):
            request_openrouter_review(
                "segredo", "system", "raio-x", model="provider/paid-model"
            )
        post.assert_not_called()

    @patch("engine_doc.ai.openrouter_client.requests.post")
    @patch("engine_doc.ai.openrouter_client.requests.get")
    def test_confirmed_free_model_calls_official_chat_endpoint(
        self, get: Mock, post: Mock
    ) -> None:
        catalog = Mock(status_code=200)
        catalog.json.return_value = {
            "data": [self._model(OPENROUTER_MODEL, "0", "0")]
        }
        get.return_value = catalog
        completion = Mock(status_code=200)
        completion.json.return_value = {
            "choices": [{"message": {"content": "análise"}}]
        }
        post.return_value = completion

        result = request_openrouter_review("segredo", "system", "raio-x")

        self.assertEqual("análise", result)
        self.assertEqual(OPENROUTER_ENDPOINT, post.call_args.args[0])
        self.assertNotIn("segredo", str(post.call_args.kwargs["json"]))


if __name__ == "__main__":
    unittest.main()

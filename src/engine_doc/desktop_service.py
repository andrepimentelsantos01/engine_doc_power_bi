"""Application service shared by the local desktop API and its tests.

The service deliberately delegates PBIP extraction, exports, prompts and AI
providers to the existing Engine Doc modules.  It only translates those
operations into small, serializable results for presentation layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .ai import (
    NVIDIA_MODEL,
    OPENROUTER_MODEL,
    NvidiaClientError,
    OpenRouterClientError,
    ReviewOutputError,
    document_ray_x,
    list_free_models,
    request_openrouter_review,
    review_ray_x,
)
from .ai.reviewer import analysis_path, documentation_path
from .cli import analyze_projects
from .discovery import discover_projects
from .exporters.text import ray_x_path


@dataclass(slots=True)
class DesktopServiceError(Exception):
    """Controlled failure safe to serialize to the desktop frontend."""

    code: str
    message: str
    status: int = 400

    def __str__(self) -> str:
        return self.message


class DesktopService:
    """Expose existing Engine Doc use cases without terminal interaction."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()

    def analyze_project(
        self, project_path: str, *, include_content: bool = True
    ) -> dict[str, Any]:
        root = self._existing_directory(project_path)
        projects = discover_projects(root)
        if not projects:
            raise DesktopServiceError(
                "invalid_project",
                "Não foi possível identificar um projeto PBIP compatível nesta pasta.",
            )
        if len(projects) > 1:
            raise DesktopServiceError(
                "multiple_projects",
                "A pasta contém mais de um projeto PBIP. Selecione a pasta de um único projeto.",
            )

        exported = analyze_projects(root, self.output_dir)
        if not exported:
            raise DesktopServiceError(
                "analysis_failed",
                "Não foi possível ler informações suficientes para gerar o raio-X.",
                422,
            )

        project, target = exported[0]
        generated = ray_x_path(target, project.name).resolve()
        try:
            content = generated.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise DesktopServiceError(
                "result_read_failed",
                "O raio-X foi gerado, mas não pôde ser aberto pela aplicação.",
                500,
            ) from None

        result = {
            "success": True,
            "project_name": project.name,
            "project_path": str(root),
            "xray_path": str(generated),
            "output_dir": str(target.resolve()),
            "warnings": list(project.warnings),
        }
        if include_content:
            result["content"] = content
        return result

    def list_openrouter_models(self, api_key: str) -> dict[str, Any]:
        key = self._required_key(api_key)
        try:
            available = list_free_models(key)
        except OpenRouterClientError as exc:
            raise self._ai_error(exc, key) from None
        finally:
            del key

        confirmed_ids = {model.id for model in available}
        if OPENROUTER_MODEL not in confirmed_ids:
            raise DesktopServiceError(
                "free_model_unavailable",
                "Não foi possível confirmar a opção automática gratuita no OpenRouter.",
                503,
            )

        models = [
            {
                **asdict(model),
                "automatic": model.id == OPENROUTER_MODEL,
            }
            for model in available
        ]
        models.sort(key=lambda item: (not item["automatic"], item["name"].casefold()))
        return {"success": True, "models": models}

    def generate_ai(
        self,
        *,
        mode: str,
        provider: str,
        api_key: str,
        xray_path_value: str,
        model: str | None = None,
        include_content: bool = True,
    ) -> dict[str, Any]:
        source = self._managed_xray(xray_path_value)
        key = self._required_key(api_key)
        provider_key = provider.strip().casefold()
        mode_key = mode.strip().casefold()

        if mode_key == "critical_analysis":
            processor = review_ray_x
            result_type = "critical_analysis"
        elif mode_key == "documentation":
            processor = document_ray_x
            result_type = "documentation"
        else:
            raise DesktopServiceError(
                "invalid_mode",
                "Selecione análise crítica ou documentação executiva/técnica.",
            )

        options: dict[str, Any]
        if provider_key == "nvidia":
            provider_label = "NVIDIA NIM"
            selected_model = NVIDIA_MODEL
            options = {"provider": provider_label, "model": selected_model}
        elif provider_key == "openrouter":
            provider_label = "OpenRouter"
            selected_model = (model or OPENROUTER_MODEL).strip()
            if not selected_model:
                selected_model = OPENROUTER_MODEL

            def openrouter_client(
                request_key: str, system_prompt: str, user_prompt: str
            ) -> str:
                return request_openrouter_review(
                    request_key,
                    system_prompt,
                    user_prompt,
                    model=selected_model,
                )

            options = {
                "provider": provider_label,
                "model": selected_model,
                "client": openrouter_client,
            }
        else:
            raise DesktopServiceError(
                "invalid_provider",
                "Selecione NVIDIA NIM ou OpenRouter.",
            )

        try:
            destination = processor(source, key, **options).resolve()
            content = destination.read_text(encoding="utf-8")
        except (NvidiaClientError, OpenRouterClientError, ReviewOutputError) as exc:
            raise self._ai_error(exc, key) from None
        except FileNotFoundError:
            raise DesktopServiceError(
                "xray_not_found",
                "O arquivo de raio-X não foi encontrado. Gere o raio-X novamente.",
                404,
            ) from None
        except (OSError, UnicodeError):
            raise DesktopServiceError(
                "result_write_failed",
                "Não foi possível gravar ou abrir o arquivo produzido pela IA.",
                500,
            ) from None
        finally:
            del key

        result = {
            "success": True,
            "type": result_type,
            "provider": provider_label,
            "model": selected_model,
            "output_path": str(destination),
            "output_dir": str(destination.parent),
        }
        if include_content:
            result["content"] = content
        return result

    def existing_results(
        self, xray_path_value: str, *, include_content: bool = True
    ) -> dict[str, Any]:
        """Return optional AI artifacts already stored beside a managed X-ray."""
        source = self._managed_xray(xray_path_value)
        results: dict[str, Any] = {"success": True}
        for key, candidate in (
            ("critical_analysis", analysis_path(source)),
            ("documentation", documentation_path(source)),
        ):
            if candidate.is_file():
                try:
                    stored = {"output_path": str(candidate.resolve())}
                    if include_content:
                        stored["content"] = candidate.read_text(encoding="utf-8")
                    results[key] = stored
                except (OSError, UnicodeError):
                    continue
        return results

    @staticmethod
    def _existing_directory(value: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise DesktopServiceError(
                "invalid_path", "Selecione a pasta do projeto PBIP."
            )
        candidate = Path(value.strip()).expanduser()
        if not candidate.is_absolute() or not candidate.exists() or not candidate.is_dir():
            raise DesktopServiceError(
                "invalid_path", "A pasta selecionada não existe ou não pode ser acessada."
            )
        return candidate.resolve()

    def _managed_xray(self, value: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise DesktopServiceError(
                "xray_not_found", "Gere o raio-X antes de utilizar a IA.", 404
            )
        candidate = Path(value.strip()).resolve()
        try:
            candidate.relative_to(self.output_dir)
        except ValueError:
            raise DesktopServiceError(
                "unmanaged_xray",
                "O arquivo informado não pertence à saída gerenciada pelo Engine Doc.",
                403,
            ) from None
        if not candidate.is_file() or not candidate.name.endswith("_raio_x.txt"):
            raise DesktopServiceError(
                "xray_not_found", "O arquivo de raio-X não foi encontrado.", 404
            )
        return candidate

    @staticmethod
    def _required_key(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise DesktopServiceError(
                "missing_api_key", "Informe a API Key do provedor selecionado."
            )
        return value.strip()

    @staticmethod
    def _ai_error(exc: Exception, api_key: str) -> DesktopServiceError:
        raw_message = str(exc).replace(api_key, "[credencial removida]")
        lowered = raw_message.casefold()
        kind = getattr(exc, "kind", "")
        if kind == "auth" or "autenticar" in lowered or "api key" in lowered:
            return DesktopServiceError(
                "authentication",
                "Não foi possível autenticar no provedor. Verifique sua API Key.",
                401,
            )
        if kind == "rate_limit" or "limite de requisi" in lowered:
            return DesktopServiceError(
                "rate_limit",
                "O provedor atingiu o limite de requisições. Tente novamente mais tarde.",
                429,
            )
        if kind == "context" or "contexto" in lowered:
            return DesktopServiceError(
                "context_limit",
                "O conteúdo do projeto excede o limite suportado pelo modelo selecionado.",
                422,
            )
        if kind == "timeout" or "demorou" in lowered or "tempo excedido" in lowered:
            return DesktopServiceError(
                "timeout", "O provedor demorou mais que o esperado para responder.", 504
            )
        if "conectar" in lowered or kind in {"catalog", "service"}:
            return DesktopServiceError(
                "connection", "Não foi possível conectar ao provedor.", 503
            )
        if isinstance(exc, ReviewOutputError):
            return DesktopServiceError(
                "invalid_ai_output",
                "O provedor retornou um conteúdo incompleto. Tente novamente.",
                502,
            )
        return DesktopServiceError(
            "provider_error",
            "Não foi possível concluir o processamento com IA.",
            502,
        )

"""Minimal OpenRouter HTTP client with safe free-model discovery."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    import requests
except ModuleNotFoundError:  # extraction must remain usable without the AI dependency
    requests = None  # type: ignore[assignment]


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_ENDPOINT = "https://openrouter.ai/api/v1/models"
OPENROUTER_MODEL = "openrouter/free"
OPENROUTER_TIMEOUT_SECONDS = 180
OPENROUTER_CATALOG_TIMEOUT_SECONDS = 30
OPENROUTER_TEMPERATURE = 0.3


class OpenRouterClientError(Exception):
    """Controlled, user-facing OpenRouter integration failure."""

    def __init__(self, message: str, *, kind: str = "service") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class OpenRouterModel:
    """Free text model returned by the official OpenRouter catalog."""

    id: str
    name: str
    context_length: int | None = None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _safe_error_detail(response: Any, api_key: str) -> str:
    try:
        body = response.json()
    except (ValueError, TypeError):
        return ""
    detail: Any = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or error.get("detail") or ""
        detail = detail or body.get("detail") or body.get("message") or ""
    if isinstance(detail, (dict, list)):
        detail = str(detail)
    if not isinstance(detail, str):
        return ""
    return " ".join(detail.split()).replace(api_key, "[credencial removida]")[:500]


def _price_is_zero(value: Any, *, missing_is_zero: bool = False) -> bool:
    if value is None:
        return missing_is_zero
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError):
        return False


def _is_free_text_model(item: dict[str, Any]) -> bool:
    architecture = item.get("architecture")
    pricing = item.get("pricing")
    if not isinstance(architecture, dict) or not isinstance(pricing, dict):
        return False

    inputs = architecture.get("input_modalities")
    outputs = architecture.get("output_modalities")
    supports_text = (
        isinstance(inputs, list)
        and "text" in inputs
        and isinstance(outputs, list)
        and "text" in outputs
    )
    if not supports_text:
        return False

    return (
        _price_is_zero(pricing.get("prompt"))
        and _price_is_zero(pricing.get("completion"))
        and _price_is_zero(pricing.get("request"), missing_is_zero=True)
    )


def list_free_models(api_key: str) -> list[OpenRouterModel]:
    """Return text-capable free models using only official catalog metadata."""
    if not api_key or not api_key.strip():
        raise OpenRouterClientError(
            "A OpenRouter API Key não foi informada.", kind="auth"
        )
    if requests is None:
        raise OpenRouterClientError(
            "A dependência 'requests' não está instalada. Execute: pip install -r requirements.txt",
            kind="dependency",
        )

    try:
        response = requests.get(
            OPENROUTER_MODELS_ENDPOINT,
            headers=_headers(api_key),
            params={
                "input_modalities": "text",
                "output_modalities": "text",
                "sort": "context-high-to-low",
            },
            timeout=OPENROUTER_CATALOG_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise OpenRouterClientError(
            "O catálogo do OpenRouter demorou mais que o esperado para responder.",
            kind="catalog",
        ) from None
    except requests.ConnectionError:
        raise OpenRouterClientError(
            "Não foi possível consultar o catálogo de modelos do OpenRouter.",
            kind="catalog",
        ) from None
    except requests.RequestException:
        raise OpenRouterClientError(
            "Não foi possível consultar o catálogo de modelos do OpenRouter.",
            kind="catalog",
        ) from None

    if response.status_code in {401, 403}:
        raise OpenRouterClientError(
            "Não foi possível autenticar no OpenRouter. Verifique sua API Key.",
            kind="auth",
        )
    if response.status_code == 429:
        raise OpenRouterClientError(
            "O limite de consultas ao catálogo do OpenRouter foi atingido.",
            kind="catalog",
        )
    if not 200 <= response.status_code < 300:
        raise OpenRouterClientError(
            f"O catálogo do OpenRouter retornou HTTP {response.status_code}.",
            kind="catalog",
        )

    try:
        body = response.json()
        data = body["data"]
    except (ValueError, TypeError, KeyError):
        raise OpenRouterClientError(
            "O catálogo do OpenRouter retornou uma resposta inválida.",
            kind="catalog",
        ) from None
    if not isinstance(data, list):
        raise OpenRouterClientError(
            "O catálogo do OpenRouter retornou uma resposta inválida.",
            kind="catalog",
        )

    models: dict[str, OpenRouterModel] = {}
    for item in data:
        if not isinstance(item, dict) or not _is_free_text_model(item):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        name = item.get("name")
        context = item.get("context_length")
        models[model_id] = OpenRouterModel(
            id=model_id,
            name=name.strip() if isinstance(name, str) and name.strip() else model_id,
            context_length=context if isinstance(context, int) and context > 0 else None,
        )

    return sorted(
        models.values(),
        key=lambda model: (-(model.context_length or 0), model.name.casefold()),
    )


def confirm_free_model(api_key: str, model_id: str) -> bool:
    """Recheck the official catalog immediately before a paid-risk request."""
    return any(model.id == model_id for model in list_free_models(api_key))


def _extract_text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise OpenRouterClientError(
            "O OpenRouter retornou uma resposta que não pôde ser interpretada."
        ) from None

    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        text = "\n".join(part.strip() for part in parts if part.strip())
        if text:
            return text
    raise OpenRouterClientError(
        "O OpenRouter retornou uma resposta que não pôde ser interpretada."
    )


def request_review(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = OPENROUTER_MODEL,
) -> str:
    """Submit the shared review prompt through OpenRouter."""
    if not api_key or not api_key.strip():
        raise OpenRouterClientError(
            "A OpenRouter API Key não foi informada.", kind="auth"
        )
    if requests is None:
        raise OpenRouterClientError(
            "A dependência 'requests' não está instalada. Execute: pip install -r requirements.txt",
            kind="dependency",
        )

    try:
        is_confirmed_free = confirm_free_model(api_key, model)
    except OpenRouterClientError as exc:
        raise OpenRouterClientError(
            "Não foi possível confirmar que este modelo é gratuito no OpenRouter. "
            "Nenhuma requisição de análise foi realizada.",
            kind="cost_guard",
        ) from exc
    if not is_confirmed_free:
        raise OpenRouterClientError(
            "Não foi possível confirmar que este modelo é gratuito no OpenRouter. "
            "Nenhuma requisição de análise foi realizada.",
            kind="cost_guard",
        )

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "model": model,
        "stream": False,
        "temperature": OPENROUTER_TEMPERATURE,
    }
    try:
        response = requests.post(
            OPENROUTER_ENDPOINT,
            headers=_headers(api_key),
            json=payload,
            stream=False,
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise OpenRouterClientError(
            "O OpenRouter demorou mais que o esperado para responder."
        ) from None
    except requests.ConnectionError:
        raise OpenRouterClientError("Não foi possível conectar ao OpenRouter.") from None
    except requests.RequestException:
        raise OpenRouterClientError("Não foi possível conectar ao OpenRouter.") from None

    detail = _safe_error_detail(response, api_key.strip())
    detail_lower = detail.casefold()
    if response.status_code in {401, 403}:
        raise OpenRouterClientError(
            "Não foi possível autenticar no OpenRouter. Verifique sua API Key.",
            kind="auth",
        )
    if response.status_code == 429:
        raise OpenRouterClientError(
            "Limite de requisições do OpenRouter atingido. Tente novamente mais tarde.",
            kind="rate_limit",
        )
    if response.status_code == 408:
        raise OpenRouterClientError(
            "O OpenRouter encerrou a solicitação por tempo excedido.", kind="timeout"
        )
    if response.status_code in {400, 413, 422}:
        context_terms = ("context", "token", "maximum", "too long", "length")
        if any(term in detail_lower for term in context_terms):
            raise OpenRouterClientError(
                "O raio-X excedeu o contexto aceito pelo modelo selecionado. "
                "Escolha um modelo com contexto maior ou reduza manualmente o conteúdo; "
                "nenhum trecho foi removido automaticamente.",
                kind="context",
            )
        message = "O OpenRouter rejeitou os parâmetros enviados pela aplicação."
        if detail:
            message = f"{message} Detalhe: {detail}"
        raise OpenRouterClientError(message, kind="request")
    if response.status_code == 402:
        raise OpenRouterClientError(
            "O OpenRouter não conseguiu processar a solicitação gratuita. "
            "Verifique a disponibilidade do modelo e os limites da conta.",
            kind="availability",
        )
    if response.status_code in {404, 502}:
        message = "O modelo ou provedor selecionado não está disponível no OpenRouter."
        if detail:
            message = f"{message} Detalhe: {detail}"
        raise OpenRouterClientError(message, kind="availability")
    if not 200 <= response.status_code < 300:
        raise OpenRouterClientError(
            f"O OpenRouter retornou um erro HTTP {response.status_code}. Tente novamente mais tarde."
        )

    try:
        body = response.json()
    except (ValueError, TypeError):
        raise OpenRouterClientError(
            "O OpenRouter retornou uma resposta que não pôde ser interpretada."
        ) from None
    return _extract_text(body)

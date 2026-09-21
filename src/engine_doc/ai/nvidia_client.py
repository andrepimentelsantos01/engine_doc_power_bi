"""Minimal NVIDIA NIM HTTP client with credential-safe error handling."""

from __future__ import annotations

from typing import Any

try:
    import requests
except ModuleNotFoundError:  # extraction must remain usable without the AI dependency
    requests = None  # type: ignore[assignment]


NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
NVIDIA_MAX_TOKENS = 16384
NVIDIA_REASONING_BUDGET = 4096
NVIDIA_TEMPERATURE = 0.2
NVIDIA_TOP_P = 0.9
NVIDIA_TIMEOUT_SECONDS = 180


class NvidiaClientError(Exception):
    """Controlled, user-facing NVIDIA integration failure."""


def _extract_text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NvidiaClientError(
            "A NVIDIA retornou uma resposta que não pôde ser interpretada."
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
    raise NvidiaClientError("A NVIDIA retornou uma resposta que não pôde ser interpretada.")


def _safe_error_detail(response: Any, api_key: str) -> str:
    """Extract a short API validation message without exposing credentials."""
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
    sanitized = " ".join(detail.split()).replace(api_key, "[credencial removida]")
    return sanitized[:500]


def request_review(api_key: str, system_prompt: str, user_prompt: str) -> str:
    """Submit text to NVIDIA NIM and return only the assistant content."""
    if not api_key or not api_key.strip():
        raise NvidiaClientError("A NVIDIA API Key não foi informada.")
    if requests is None:
        raise NvidiaClientError(
            "A dependência 'requests' não está instalada. Execute: pip install -r requirements.txt"
        )

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "model": NVIDIA_MODEL,
        "max_tokens": NVIDIA_MAX_TOKENS,
        "reasoning_budget": NVIDIA_REASONING_BUDGET,
        "stream": False,
        "temperature": NVIDIA_TEMPERATURE,
        "top_p": NVIDIA_TOP_P,
    }

    try:
        response = requests.post(
            NVIDIA_ENDPOINT,
            headers=headers,
            json=payload,
            stream=False,
            timeout=NVIDIA_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise NvidiaClientError("A NVIDIA demorou mais que o esperado para responder.") from None
    except requests.ConnectionError:
        raise NvidiaClientError("Não foi possível conectar ao serviço NVIDIA NIM.") from None
    except requests.RequestException:
        raise NvidiaClientError("Não foi possível conectar ao serviço NVIDIA NIM.") from None

    if response.status_code in {401, 403}:
        raise NvidiaClientError("Não foi possível autenticar na NVIDIA. Verifique sua API Key.")
    if response.status_code == 429:
        raise NvidiaClientError(
            "Limite de requisições da NVIDIA atingido. Tente novamente mais tarde."
        )
    if response.status_code in {400, 422}:
        detail = _safe_error_detail(response, api_key.strip())
        message = "A NVIDIA rejeitou os parâmetros enviados pela aplicação."
        if detail:
            message = f"{message} Detalhe: {detail}"
        raise NvidiaClientError(message)
    if not 200 <= response.status_code < 300:
        raise NvidiaClientError(
            f"O serviço NVIDIA retornou um erro HTTP {response.status_code}. Tente novamente mais tarde."
        )

    try:
        body = response.json()
    except (ValueError, TypeError):
        raise NvidiaClientError(
            "A NVIDIA retornou uma resposta que não pôde ser interpretada."
        ) from None
    return _extract_text(body)

"""Optional AI review layer.

This package never reads PBIP artifacts. It receives only the final text X-ray.
"""

from .nvidia_client import NVIDIA_MODEL, NvidiaClientError
from .openrouter_client import (
    OPENROUTER_MODEL,
    OpenRouterClientError,
    OpenRouterModel,
    confirm_free_model,
    list_free_models,
    request_review as request_openrouter_review,
)
from .reviewer import ReviewOutputError, document_ray_x, review_ray_x

__all__ = [
    "NVIDIA_MODEL",
    "NvidiaClientError",
    "OPENROUTER_MODEL",
    "OpenRouterClientError",
    "OpenRouterModel",
    "confirm_free_model",
    "list_free_models",
    "request_openrouter_review",
    "ReviewOutputError",
    "document_ray_x",
    "review_ray_x",
]

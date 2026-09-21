"""Optional NVIDIA NIM review layer.

This package never reads PBIP artifacts. It receives only the final text X-ray.
"""

from .nvidia_client import NVIDIA_MODEL, NvidiaClientError
from .reviewer import review_ray_x

__all__ = ["NVIDIA_MODEL", "NvidiaClientError", "review_ray_x"]


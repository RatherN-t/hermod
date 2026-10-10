"""Thin wrapper over LiteLLM so the model is one env var (LLM_MODEL).

Every call goes through the harness, so nothing reaches the model unlogged.
"""
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    latency_ms: int = 0


async def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    raise NotImplementedError


async def extract_prescription_from_image(image_bytes: bytes, mime_type: str) -> dict:
    """Vision call: prescription photo -> structured medications (for doctor review)."""
    raise NotImplementedError

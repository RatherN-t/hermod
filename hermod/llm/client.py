"""Thin wrapper over LiteLLM so the model is one env var (LLM_MODEL).

Every call goes through the harness, so nothing reaches the model unlogged.
"""
import json
import time
from dataclasses import dataclass, field

import litellm

from hermod.config import get_settings


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # [{id, name, arguments: dict}]
    latency_ms: int = 0

    def assistant_message(self) -> dict:
        """The assistant turn in OpenAI format, to append before the tool results."""
        msg: dict = {"role": "assistant", "content": self.text or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])},
                }
                for c in self.tool_calls
            ]
        return msg


async def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    settings = get_settings()
    start = time.perf_counter()
    resp = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
        tools=tools or None,
        api_key=settings.gemini_api_key or None,
    )
    msg = resp.choices[0].message
    calls = []
    for c in msg.tool_calls or []:
        try:
            args = json.loads(c.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": c.id, "name": c.function.name, "arguments": args})
    return LLMResult(
        text=msg.content or "",
        tool_calls=calls,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


async def extract_prescription_from_image(image_bytes: bytes, mime_type: str) -> dict:
    """Vision call: prescription photo -> structured medications (for doctor review)."""
    raise NotImplementedError

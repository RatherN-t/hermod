"""The harness: wraps every agent turn, records an AgentTrace, enforces guardrails."""
from hermod.llm.client import LLMResult


async def traced_completion(
    *, patient_id: int | None, trigger: str, messages: list[dict], tools: list[dict] | None
) -> LLMResult:
    """Call the LLM, persist prompt/output/tool calls/latency/error, return the result."""
    raise NotImplementedError

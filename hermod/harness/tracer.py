"""The harness: wraps every agent turn, records an AgentTrace, enforces guardrails."""
import json
import time

from hermod.config import get_settings
from hermod.db.models import AgentTrace
from hermod.db.session import new_session
from hermod.llm import client
from hermod.llm.client import LLMResult


async def traced_completion(
    *, patient_id: int | None, trigger: str, messages: list[dict], tools: list[dict] | None
) -> LLMResult:
    """Call the LLM, persist prompt/output/tool calls/latency/error, return the result."""
    trace = AgentTrace(
        patient_id=patient_id,
        trigger=trigger,
        model=get_settings().llm_model,
        prompt_json=json.dumps(messages, default=str),
    )
    start = time.perf_counter()
    try:
        result = await client.complete(messages, tools)
        trace.output_text = result.text
        trace.tool_calls_json = json.dumps(result.tool_calls, default=str)
        return result
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
        raise
    finally:
        trace.latency_ms = int((time.perf_counter() - start) * 1000)
        with new_session() as s:
            s.add(trace)
            s.commit()

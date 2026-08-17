import os
import uuid
import json
from functools import lru_cache

# ── 1. Load configuration before importing the agent ────────────────────────

def _bootstrap_env() -> None:
    """Load local environment variables for development."""

    # .env file (local development)
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass

_bootstrap_env()

# ── 2. Import agent (env vars must be set first) ─────────────────────────────

@lru_cache(maxsize=1)
def _get_agent_components():
    from PromptBasedAgent import graph  # noqa: E402
    from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
    return graph, AIMessage, HumanMessage


def warmup_agent() -> None:
    """Initialize the agent once so later requests are faster."""
    graph, AIMessage, HumanMessage = _get_agent_components()
    # add choices to history 
    

# ── 3. Helpers ────────────────────────────────────────────────────────────────

def make_thread_id(seed: str) -> str:
    """Return a deterministic UUID5 from the session seed."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def _extract_json_after_marker(text: str, marker: str):
    """If `marker` appears in `text`, find and parse the JSON object that follows.

    Returns a tuple (leading_text, parsed_json_or_None).
    """
    idx = text.find(marker)
    if idx == -1:
        return text, None

    # find first '{' after the marker
    brace_idx = text.find("{", idx + len(marker))
    if brace_idx == -1:
        return text, None

    # attempt to find the matching closing brace by counting
    depth = 0
    end_idx = None
    for i in range(brace_idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    if end_idx is None:
        # couldn't find balanced JSON
        return text, None

    json_text = text[brace_idx:end_idx]
    try:
        parsed = json.loads(json_text)
        leading = text[:brace_idx].strip()
        return leading, parsed
    except Exception:
        return text, None


def generate_reply(history: list[dict[str, str]], thread_id: str) -> tuple[str, dict | None]:
    """Invoke the LangGraph agent and return (text, parsed_json).

    If the agent outputs a thank-you marker followed by a JSON object, the JSON
    will be parsed and returned separately. Otherwise parsed_json is None.
    """

    graph, AIMessage, HumanMessage = _get_agent_components()

    # Build LangChain message list for the graph
    lc_messages = []
    for message in history:
        role = message.get("role", "")
        content = message.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:
        result = graph.invoke({"messages": lc_messages}, config=config)
        last = result["messages"][-1]
        if hasattr(last, "content"):
            content = str(last.content)
        else:
            content = str(last.get("content", last))

        # The prompt spec uses this exact thank-you sentence before JSON output.
        thank_you = "Thank you, your perspective helps shape what the future could become."
        leading, parsed = _extract_json_after_marker(content, thank_you)
        if parsed is not None:
            # ensure the leading contains the thank-you sentence (normalized)
            leading = thank_you
            return leading, parsed

        return content, None
    except Exception as exc:
        return f"⚠️ Error: {exc}", None

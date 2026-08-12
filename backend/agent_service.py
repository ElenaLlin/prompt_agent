import os
import uuid
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


def generate_reply(history: list[dict[str, str]], thread_id: str) -> str:
    """Invoke the LangGraph agent and return the last AI message content."""

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
            return str(last.content)
        return str(last.get("content", last))
    except Exception as exc:
        return f"⚠️ Error: {exc}"

import os
import json
import datetime
from typing import Any, TypedDict
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt


PROMPT_NAME = "agent.prompt"
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", PROMPT_NAME)
OPENAI_MODEL = "gpt-4.1-mini"

class AgentContext(TypedDict, total=False):
    choices: dict[str, Any]


def get_current_date() -> str:
    """Get today's date in ISO format."""
    return datetime.date.today().isoformat()

def _load_system_prompt(choices: dict | None = None) -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        template = f.read().strip()

    # Load choices and substitute simple {{key}} placeholders
    choices = choices or {}
    if isinstance(choices, dict):
        for k, v in choices.items():
            if isinstance(v, (str, int, float)):
                template = template.replace("{{" + k + "}}", str(v))

    # Also append the raw choices JSON so the model can reference all values
    if choices:
        template += "\n\n# INPUT DATA\n" + json.dumps(choices, indent=2, ensure_ascii=False)

    return template

@dynamic_prompt
def current_system_prompt(request: ModelRequest[AgentContext]) -> str:
    context = request.runtime.context or {}
    return _load_system_prompt(context.get("choices"))


graph = create_agent(
    model=f"openai:{OPENAI_MODEL}",
    tools=[get_current_date],
    middleware=[current_system_prompt],
    context_schema=AgentContext,
)
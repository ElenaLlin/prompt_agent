import os
import json
import datetime
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain.agents import AgentState


PROMPT_NAME = "agent.prompt"
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", PROMPT_NAME)
CHOICES_PATH = os.path.join(os.path.dirname(__file__), "choices.json")
OPENAI_MODEL = "gpt-4.1-mini"


def get_current_date() -> str:
    """Get today's date in ISO format."""
    return datetime.date.today().isoformat()

def _load_choices() -> dict:
    try:
        with open(CHOICES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _load_system_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        template = f.read().strip()

    # Load choices and substitute simple {{key}} placeholders
    choices = _load_choices()
    if isinstance(choices, dict):
        for k, v in choices.items():
            if isinstance(v, (str, int, float)):
                template = template.replace("{{" + k + "}}", str(v))

    # Also append the raw choices JSON so the model can reference all values
    if choices:
        template += "\n\n# INPUT DATA (choices.json)\n" + json.dumps(choices, indent=2, ensure_ascii=False)

    return template

base_system_prompt = _load_system_prompt()   

'''
def prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:  
    system_msg = base_system_prompt
    return [{"role": "system", "content": system_msg}] + state["messages"]
'''

graph = create_agent(
    model=f"openai:{OPENAI_MODEL}",
    tools=[get_current_date],
    system_prompt=base_system_prompt # was prompt now works
)
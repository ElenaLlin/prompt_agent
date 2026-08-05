import os
import datetime
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain.agents import AgentState


PROMPT_NAME = "agent.prompt"
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", PROMPT_NAME)
OPENAI_MODEL = "gpt-4.1-mini"


def get_current_date() -> str:
    """Get today's date in ISO format."""
    return datetime.date.today().isoformat()

def _load_system_prompt() -> str:
   with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()

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
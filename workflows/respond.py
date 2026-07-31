"""Final response generation — the one LLM call that produces the reply
sent back to the employee, phrasing whatever outcome the graph computed.
"""

from __future__ import annotations

import anthropic

from app import config
from prompts.response_generation import build_system_prompt
from workflows.state import AgentState


def response_generation_node(state: AgentState) -> dict:
    system = build_system_prompt(state["employee"], state["outcome"], state["tool_result"])
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, base_url=config.ANTHROPIC_BASE_URL)
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": state["message"]}],
    )
    return {"reply": resp.content[0].text}

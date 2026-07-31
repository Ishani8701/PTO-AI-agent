"""TimeOffBot — an agent that answers Acme Corp policy questions, checks
leave balances, submits time-off requests (with confirmation), and lists
existing requests. See coursework.md Parts 1-2 and workflows/graph.py for
the LangGraph orchestration behind /api/chat.
"""

import json
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config
from workflows.graph import run_turn

app = FastAPI(title="TimeOffBot")

_EMPLOYEES = {
    e["id"]: e for e in json.loads((config.DATA_DIR / "employees.json").read_text())
}


class ChatRequest(BaseModel):
    message: str


@app.get("/api/users")
def users():
    """The employees you can act as, shown in the UI's user switcher."""
    return list(_EMPLOYEES.values())


@app.post("/api/chat")
def chat(req: ChatRequest, x_user_id: str = Header(default="", alias="X-User-Id")):
    """Run one turn of the agent for the currently selected employee."""
    emp = _EMPLOYEES.get(x_user_id)
    if not emp:
        return {"reply": "I don't recognize you as an Acme Corp employee."}

    reply = run_turn(emp, req.message)
    return {"reply": reply}


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")

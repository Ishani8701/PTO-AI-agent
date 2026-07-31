"""Configuration — environment variables and paths for the shell."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")

# Anthropic — the agent's actual model provider (see CLAUDE.md Models).
# Azure OpenAI above is kept available for future use (e.g. as an independent
# model for evaluation, to avoid a model grading its own answers).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5")
ANTHROPIC_OPUS_MODEL = os.getenv("ANTHROPIC_OPUS_MODEL", "claude-sonnet-4-6")

# ServiceNow — live PTO API integration (coursework Part 3).
SERVICENOW_INSTANCE_URL = os.getenv("SERVICENOW_INSTANCE_URL")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")

# Google Calendar — read-only access to each employee's own calendar for the
# advisory branch's timing reasoning (see tools/calendar_client.py). Talks to
# the real Calendar REST API directly via google-api-python-client — no
# separate process needed, unlike the abandoned MCP-based approach (Google's
# Calendar MCP server returned an unresolved "caller does not have
# permission" error regardless of scope; the plain REST API works fine with
# the same account/credentials). client_id/secret are a "Desktop app" type
# OAuth client (see scripts/authorize_calendar.py for the one-time
# per-employee consent flow this pairs with).
GOOGLE_CALENDAR_CLIENT_ID = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
GOOGLE_CALENDAR_CLIENT_SECRET = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
GOOGLE_CALENDAR_SCOPE = os.getenv("GOOGLE_CALENDAR_SCOPE", "https://www.googleapis.com/auth/calendar.readonly")

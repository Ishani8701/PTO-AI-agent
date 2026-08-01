"""Google Calendar access for the advisory branch — loads/refreshes each
employee's own OAuth credentials and calls the real Calendar REST API
directly. Runs in the main app's own process/venv; no separate bridge
process needed (unlike the abandoned MCP-based approach — see
app/config.py's comment for why that path was dropped).

Same public shape (get_calendar_events, CalendarError,
CalendarNotAuthorizedError) as the old bridge-HTTP-client version it
replaces, so workflows/advisory.py's _execute_tool needed no changes at all.
"""

from __future__ import annotations

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app import config
from tracing import traced

TOKENS_DIR = config.DATA_DIR / "calendar_tokens"


class CalendarError(Exception):
    """Raised on any Calendar API failure — network error, non-2xx
    response, or the employee not having authorized calendar access yet.
    Callers should catch this and explain the failure rather than crash
    (see workflows/advisory.py's _execute_tool, which turns this into a
    graceful {"error": ...} result for Opus instead of a dead tool loop).
    """


class CalendarNotAuthorizedError(CalendarError):
    """This employee has never completed the one-time OAuth consent —
    run `python scripts/authorize_calendar.py <employee_id>` first.
    """


def _load_credentials(employee_id: str) -> Credentials:
    path = TOKENS_DIR / f"{employee_id}.json"
    if not path.exists():
        raise CalendarNotAuthorizedError(
            f"No calendar access authorized for {employee_id} yet — "
            f"run: python scripts/authorize_calendar.py {employee_id}"
        )
    creds = Credentials.from_authorized_user_file(str(path))
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        path.write_text(creds.to_json())  # persist the refreshed access token
    return creds


@traced("check_calendar")
def get_calendar_events(employee_id: str, start_date: str, end_date: str) -> list[dict]:
    creds = _load_credentials(employee_id)
    service = build("calendar", "v3", credentials=creds)

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=f"{start_date}T00:00:00Z",
                timeMax=f"{end_date}T23:59:59Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except HttpError as e:
        raise CalendarError(f"Google Calendar API returned an error: {e}") from e

    return [
        {
            "summary": item.get("summary", "(no title)"),
            "start": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
            "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
        }
        for item in result.get("items", [])
    ]

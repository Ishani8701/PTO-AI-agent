"""One-time interactive OAuth consent for a single mock employee's dummy
Google account. This is an admin/setup step, not a product feature — run it
once per employee, using their dummy Google account, before that employee
can use calendar-aware advisory reasoning (see tools/calendar_client.py).

InstalledAppFlow.run_local_server() handles the whole interactive dance
(open the browser, catch Google's redirect, exchange the code) in one call —
no custom callback server needed, unlike the abandoned MCP-based approach.
access_type="offline" + prompt="consent" are passed explicitly since neither
is the library's default, and both are required to get a refresh token back
(without one, the access token — ~1hr lifetime — would need fresh consent
every hour instead of ever staying silent).

Run: python3 -m scripts.authorize_calendar E002
"""

from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from app import config

_CLIENT_CONFIG = {
    "installed": {
        "client_id": config.GOOGLE_CALENDAR_CLIENT_ID,
        "client_secret": config.GOOGLE_CALENDAR_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def authorize(employee_id: str) -> None:
    if not config.GOOGLE_CALENDAR_CLIENT_ID or not config.GOOGLE_CALENDAR_CLIENT_SECRET:
        raise SystemExit(
            "GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET are not set in .env — "
            "create a Desktop app OAuth client in Google Cloud Console first."
        )

    flow = InstalledAppFlow.from_client_config(_CLIENT_CONFIG, scopes=[config.GOOGLE_CALENDAR_SCOPE])
    creds = flow.run_local_server(port=8100, access_type="offline", prompt="consent")

    tokens_dir = config.DATA_DIR / "calendar_tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    (tokens_dir / f"{employee_id}.json").write_text(creds.to_json())

    print(f"Authorized {employee_id} — token cached, calendar access won't prompt again for them.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 -m scripts.authorize_calendar <employee_id>")
    authorize(sys.argv[1])

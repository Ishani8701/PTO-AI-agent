"""One-off check that the ServiceNow Table API is actually reachable from
this lab instance with Basic Auth, before building anything on top of it.

Run: python3 -m scripts.servicenow_smoke_test
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
username = os.getenv("SERVICENOW_USERNAME")
password = os.getenv("SERVICENOW_PASSWORD")

if not (instance_url and username and password):
    raise SystemExit(
        "Missing SERVICENOW_INSTANCE_URL / SERVICENOW_USERNAME / SERVICENOW_PASSWORD "
        "in .env — fill those in first."
    )

resp = requests.get(
    f"{instance_url}/api/now/table/sys_user",
    params={"sysparm_limit": 1},
    auth=(username, password),
    headers={"Accept": "application/json"},
    timeout=10,
)

print("Status:", resp.status_code)
print("Body:", resp.text[:500])

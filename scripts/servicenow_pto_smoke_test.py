"""Confirms the custom u_pto_balance / u_pto_request tables are reachable
and writable via the Table API before any real integration code is built.
Inserts a throwaway test record, reads it back, then deletes it.

Run: python3 -m scripts.servicenow_pto_smoke_test
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
username = os.getenv("SERVICENOW_USERNAME")
password = os.getenv("SERVICENOW_PASSWORD")

if not (instance_url and username and password):
    raise SystemExit("Missing SERVICENOW_INSTANCE_URL / SERVICENOW_USERNAME / SERVICENOW_PASSWORD in .env")

auth = (username, password)
headers = {"Accept": "application/json", "Content-Type": "application/json"}


def get(table, params=None):
    resp = requests.get(f"{instance_url}/api/now/table/{table}", params=params, auth=auth, headers=headers, timeout=10)
    print(f"GET {table} ->", resp.status_code)
    return resp


print("=== Reachability ===")
get("u_pto_balance", {"sysparm_limit": 1})
get("u_pto_request", {"sysparm_limit": 1})

print("\n=== Write round-trip on u_pto_balance ===")
create_resp = requests.post(
    f"{instance_url}/api/now/table/u_pto_balance",
    json={"u_employee_id": "TEST", "u_leave_type": "test", "u_remaining_days": 0},
    auth=auth,
    headers=headers,
    timeout=10,
)
print("POST ->", create_resp.status_code)
body = create_resp.json()
print(body)

sys_id = body.get("result", {}).get("sys_id")
if sys_id:
    read_resp = get("u_pto_balance", {"sysparm_query": f"sys_id={sys_id}"})
    print(read_resp.json())

    delete_resp = requests.delete(
        f"{instance_url}/api/now/table/u_pto_balance/{sys_id}", auth=auth, headers=headers, timeout=10
    )
    print("DELETE (cleanup) ->", delete_resp.status_code)

"""One-time migration: seed the ServiceNow u_pto_balance / u_pto_request
tables from the existing local JSON mock data, preserving current state
(approved/pending/rejected statuses as they are) rather than resetting to
a clean slate. Not idempotent — running this twice will duplicate records,
since it's meant to be run once as a one-time migration, not repeatedly.

Run: python3 -m scripts.seed_servicenow
"""

import json

from app import config
from tools.servicenow_client import create

balances = json.loads((config.DATA_DIR / "balances.json").read_text())
for b in balances:
    create(
        "u_pto_balance",
        {
            "u_employee_id": b["employee_id"],
            "u_leave_type": b["leave_type"],
            "u_remaining_days": b["remaining_days"],
        },
    )
print(f"Seeded {len(balances)} balance records.")

requests = json.loads((config.DATA_DIR / "requests.json").read_text())
for r in requests:
    created = create(
        "u_pto_request",
        {
            "u_employee_id": r["employee_id"],
            "u_leave_type": r["leave_type"],
            "u_start_date": r["start_date"],
            "u_end_date": r["end_date"],
            "u_status": r["status"],
        },
    )
    print(f"  {r['id']} -> {created['u_number']}")
print(f"Seeded {len(requests)} request records.")

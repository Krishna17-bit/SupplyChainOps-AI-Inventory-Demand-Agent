from __future__ import annotations

import io
import json
from typing import Dict

import pandas as pd


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def make_excel_workbook(model: Dict, report_text: str) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for key in ["inventory_health", "reorder_plan", "supplier_risk", "anomalies"]:
            df = model.get(key)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.replace([float("inf"), float("-inf")], None).to_excel(writer, sheet_name=key[:31], index=False)
        pd.DataFrame(model.get("alerts", [])).to_excel(writer, sheet_name="alerts", index=False)
        pd.DataFrame(model.get("automation_playbooks", [])).to_excel(writer, sheet_name="automation", index=False)
        pd.DataFrame([model.get("kpis", {})]).to_excel(writer, sheet_name="kpis", index=False)
        pd.DataFrame({"report": report_text.splitlines()}).to_excel(writer, sheet_name="report", index=False)
    return output.getvalue()


def make_automation_json(model: Dict, webhook_url: str = "") -> str:
    payload = {
        "source": "SupplyChainOps AI",
        "webhook_url_placeholder": webhook_url,
        "automation_playbooks": model.get("automation_playbooks", []),
        "alerts": model.get("alerts", [])[:100],
        "approval_policy": {
            "auto_create_po": False,
            "auto_send_supplier_email": False,
            "require_human_approval_for_order_value_above": 0,
            "safe_mode": True,
        },
    }
    return json.dumps(payload, indent=2, default=str)

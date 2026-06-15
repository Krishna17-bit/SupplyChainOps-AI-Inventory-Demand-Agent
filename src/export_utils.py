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
        sheet_mapping = {
            "inventory_health": "inventory_health",
            "reorder_plan": "reorder_plan",
            "supplier_risk": "supplier_risk",
            "anomalies": "anomalies",
            "sku_returns": "sku_returns",
            "supplier_returns": "supplier_returns",
            "transfers": "transfers",
            "bom": "bom_recipes",
            "freight_comparisons": "freight_optimization",
            "financial_kpis": "financial_kpis"
        }
        for key, sheet_name in sheet_mapping.items():
            df = model.get(key)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.replace([float("inf"), float("-inf")], None).to_excel(writer, sheet_name=sheet_name, index=False)
        pd.DataFrame(model.get("alerts", [])).to_excel(writer, sheet_name="alerts", index=False)
        pd.DataFrame(model.get("automation_playbooks", [])).to_excel(writer, sheet_name="automation", index=False)
        pd.DataFrame([model.get("kpis", {})]).to_excel(writer, sheet_name="kpis", index=False)
        pd.DataFrame({"report": report_text.splitlines()}).to_excel(writer, sheet_name="report", index=False)
    return output.getvalue()


def make_automation_json(model: Dict, webhook_url: str = "") -> str:
    transfers = model.get("transfers")
    transfers_list = transfers.to_dict(orient="records") if isinstance(transfers, pd.DataFrame) else transfers
    payload = {
        "source": "SupplyChainOps AI",
        "webhook_url_placeholder": webhook_url,
        "automation_playbooks": model.get("automation_playbooks", []),
        "alerts": model.get("alerts", [])[:100],
        "transfers": transfers_list,
        "approval_policy": {
            "auto_create_po": False,
            "auto_send_supplier_email": False,
            "require_human_approval_for_order_value_above": 0,
            "safe_mode": True,
        },
    }
    return json.dumps(payload, indent=2, default=str)

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def _find_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    if df is None or df.empty:
        return None
    normalized = {_norm(c): c for c in df.columns}
    for cand in candidates:
        if _norm(cand) in normalized:
            return normalized[_norm(cand)]
    # fuzzy contains
    for cand in candidates:
        n = _norm(cand)
        for k, orig in normalized.items():
            if n in k or k in n:
                return orig
    return None


def infer_role(table_name: str, df: pd.DataFrame) -> str:
    n = _norm(table_name)
    cols = " ".join(_norm(c) for c in df.columns)
    text = n + " " + cols
    if any(x in text for x in ["purchase_order", "po_id", "ordered_qty", "expected_date"]):
        return "purchase_orders"
    if any(x in text for x in ["supplier", "vendor", "lead_time", "defect_rate", "on_time"]):
        return "suppliers"
    if any(x in text for x in ["stock_on_hand", "inventory", "warehouse", "reorder", "stock_quantity"]):
        return "inventory"
    if any(x in text for x in ["return", "refund", "return_qty"]):
        return "returns"
    if any(x in text for x in ["sales", "order_date", "quantity_sold", "revenue", "profit"]):
        return "sales"
    return "other"


def pick_tables(tables: Dict[str, pd.DataFrame]) -> Dict[str, str | None]:
    roles = {"sales": None, "inventory": None, "suppliers": None, "purchase_orders": None, "returns": None}
    for name, df in tables.items():
        role = infer_role(name, df)
        if role in roles and roles[role] is None:
            roles[role] = name
    return roles


def standardize_sales(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date","sku","product","qty","revenue","cost","profit","region","channel","segment"])
    d = df.copy()
    date = _find_col(d, ["date","order_date","sale_date","transaction_date","created_at","invoice_date"])
    sku = _find_col(d, ["sku","product_id","item_id","item_code","product_code"])
    product = _find_col(d, ["product","product_name","item","item_name","name"])
    qty = _find_col(d, ["quantity_sold","quantity","qty","units","units_sold","sold_qty"])
    revenue = _find_col(d, ["revenue","sales","amount","total","gross_sales","net_sales"])
    cost = _find_col(d, ["cost","cogs","total_cost","purchase_cost"])
    profit = _find_col(d, ["profit","gross_profit","margin_value"])
    region = _find_col(d, ["region","state","city","country","market"])
    channel = _find_col(d, ["channel","source","store","platform"])
    segment = _find_col(d, ["segment","customer_segment","customer_type","tier"])

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(d[date], errors="coerce") if date else pd.Timestamp.today().normalize()
    out["sku"] = d[sku].astype(str) if sku else "UNKNOWN"
    out["product"] = d[product].astype(str) if product else out["sku"]
    out["qty"] = pd.to_numeric(d[qty], errors="coerce").fillna(1) if qty else 1
    out["revenue"] = pd.to_numeric(d[revenue], errors="coerce") if revenue else np.nan
    if out["revenue"].isna().all():
        price = _find_col(d, ["unit_price","price","selling_price"])
        if price:
            out["revenue"] = out["qty"] * pd.to_numeric(d[price], errors="coerce").fillna(0)
        else:
            out["revenue"] = 0.0
    out["cost"] = pd.to_numeric(d[cost], errors="coerce") if cost else np.nan
    if out["cost"].isna().all():
        unit_cost = _find_col(d, ["unit_cost","cost_per_unit"])
        out["cost"] = out["qty"] * pd.to_numeric(d[unit_cost], errors="coerce").fillna(0) if unit_cost else 0.0
    out["profit"] = pd.to_numeric(d[profit], errors="coerce") if profit else out["revenue"] - out["cost"]
    out["region"] = d[region].astype(str) if region else "Unassigned"
    out["channel"] = d[channel].astype(str) if channel else "Unassigned"
    out["segment"] = d[segment].astype(str) if segment else "Unassigned"
    out = out.dropna(subset=["date"])
    out["qty"] = out["qty"].clip(lower=0)
    return out


def standardize_inventory(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["sku","product","stock","unit_cost","supplier_id","warehouse","min_order_qty"])
    d = df.copy()
    sku = _find_col(d, ["sku","product_id","item_id","item_code","product_code"])
    product = _find_col(d, ["product","product_name","item","item_name","name"])
    stock = _find_col(d, ["stock_on_hand","stock","inventory","stock_quantity","qty_on_hand","available_qty"])
    unit_cost = _find_col(d, ["unit_cost","cost","purchase_cost","standard_cost"])
    supplier = _find_col(d, ["supplier_id","vendor_id","supplier","vendor"])
    warehouse = _find_col(d, ["warehouse","location","dc","fulfillment_center"])
    moq = _find_col(d, ["min_order_qty","moq","minimum_order_quantity"])
    out = pd.DataFrame()
    out["sku"] = d[sku].astype(str) if sku else d.index.astype(str)
    out["product"] = d[product].astype(str) if product else out["sku"]
    out["stock"] = pd.to_numeric(d[stock], errors="coerce").fillna(0) if stock else 0
    out["unit_cost"] = pd.to_numeric(d[unit_cost], errors="coerce").fillna(0) if unit_cost else 0
    out["supplier_id"] = d[supplier].astype(str) if supplier else "UNKNOWN"
    out["warehouse"] = d[warehouse].astype(str) if warehouse else "Unassigned"
    out["min_order_qty"] = pd.to_numeric(d[moq], errors="coerce").fillna(1) if moq else 1
    return out


def standardize_suppliers(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["supplier_id","supplier_name","lead_time_days","lead_time_std_days","on_time_rate","defect_rate","country","payment_terms","min_order_value"])
    d = df.copy()
    sid = _find_col(d, ["supplier_id","vendor_id","supplier","vendor"])
    name = _find_col(d, ["supplier_name","vendor_name","name","supplier"])
    lead = _find_col(d, ["lead_time_days","lead_time","avg_lead_time","delivery_days"])
    lead_std = _find_col(d, ["lead_time_std_days","lead_time_std","delay_std","lead_time_variability"])
    otr = _find_col(d, ["on_time_rate","on_time_delivery","otd","service_level"])
    defect = _find_col(d, ["defect_rate","return_rate","quality_issue_rate"])
    country = _find_col(d, ["country","region","location"])
    terms = _find_col(d, ["payment_terms","terms"])
    mov = _find_col(d, ["min_order_value","minimum_order_value","mov"])
    out = pd.DataFrame()
    out["supplier_id"] = d[sid].astype(str) if sid else d.index.astype(str)
    out["supplier_name"] = d[name].astype(str) if name else out["supplier_id"]
    out["lead_time_days"] = pd.to_numeric(d[lead], errors="coerce").fillna(10) if lead else 10
    out["lead_time_std_days"] = pd.to_numeric(d[lead_std], errors="coerce").fillna(3) if lead_std else 3
    out["on_time_rate"] = pd.to_numeric(d[otr], errors="coerce").fillna(.85) if otr else .85
    out.loc[out["on_time_rate"] > 1, "on_time_rate"] = out.loc[out["on_time_rate"] > 1, "on_time_rate"] / 100
    out["defect_rate"] = pd.to_numeric(d[defect], errors="coerce").fillna(.02) if defect else .02
    out.loc[out["defect_rate"] > 1, "defect_rate"] = out.loc[out["defect_rate"] > 1, "defect_rate"] / 100
    out["country"] = d[country].astype(str) if country else "Unknown"
    out["payment_terms"] = d[terms].astype(str) if terms else "Unknown"
    out["min_order_value"] = pd.to_numeric(d[mov], errors="coerce").fillna(0) if mov else 0
    return out


def standardize_pos(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["po_id","sku","supplier_id","ordered_qty","status","order_date","expected_date","unit_cost"])
    d = df.copy()
    po = _find_col(d, ["po_id","purchase_order","order_id"])
    sku = _find_col(d, ["sku","product_id","item_id","item_code","product_code"])
    supplier = _find_col(d, ["supplier_id","vendor_id","supplier","vendor"])
    qty = _find_col(d, ["ordered_qty","quantity","qty","po_qty","order_qty"])
    status = _find_col(d, ["status","po_status","state"])
    order_date = _find_col(d, ["order_date","created_at","po_date"])
    expected = _find_col(d, ["expected_date","eta","delivery_date","expected_delivery"])
    unit_cost = _find_col(d, ["unit_cost","cost","purchase_cost"])
    out = pd.DataFrame()
    out["po_id"] = d[po].astype(str) if po else d.index.astype(str)
    out["sku"] = d[sku].astype(str) if sku else "UNKNOWN"
    out["supplier_id"] = d[supplier].astype(str) if supplier else "UNKNOWN"
    out["ordered_qty"] = pd.to_numeric(d[qty], errors="coerce").fillna(0) if qty else 0
    out["status"] = d[status].astype(str).str.lower() if status else "open"
    out["order_date"] = pd.to_datetime(d[order_date], errors="coerce") if order_date else pd.Timestamp.today().normalize()
    out["expected_date"] = pd.to_datetime(d[expected], errors="coerce") if expected else pd.Timestamp.today().normalize() + pd.Timedelta(days=10)
    out["unit_cost"] = pd.to_numeric(d[unit_cost], errors="coerce").fillna(0) if unit_cost else 0
    return out


def standardize_returns(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date","sku","return_qty","reason","refund_amount"])
    d = df.copy()
    date = _find_col(d, ["return_date","date","created_at"])
    sku = _find_col(d, ["sku","product_id","item_id","product_code"])
    qty = _find_col(d, ["return_qty","quantity","qty"])
    reason = _find_col(d, ["reason","return_reason","category"])
    refund = _find_col(d, ["refund_amount","amount","refund","value"])
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(d[date], errors="coerce") if date else pd.Timestamp.today().normalize()
    out["sku"] = d[sku].astype(str) if sku else "UNKNOWN"
    out["return_qty"] = pd.to_numeric(d[qty], errors="coerce").fillna(1) if qty else 1
    out["reason"] = d[reason].astype(str) if reason else "Unassigned"
    out["refund_amount"] = pd.to_numeric(d[refund], errors="coerce").fillna(0) if refund else 0
    return out.dropna(subset=["date"])


def z_for_service(service_level: float) -> float:
    # Common service-level approximations.
    if service_level >= .99:
        return 2.33
    if service_level >= .98:
        return 2.05
    if service_level >= .95:
        return 1.65
    if service_level >= .90:
        return 1.28
    if service_level >= .85:
        return 1.04
    return .84


def build_supply_model(tables: Dict[str, pd.DataFrame], role_map: Dict[str, str | None], horizon_days: int = 30, service_level: float = .95, order_cost: float = 35, holding_cost_rate: float = .22, demand_multiplier: float = 1.0, lead_time_delay_days: float = 0) -> Dict:
    sales = standardize_sales(tables.get(role_map.get("sales")) if role_map.get("sales") else None)
    inv = standardize_inventory(tables.get(role_map.get("inventory")) if role_map.get("inventory") else None)
    suppliers = standardize_suppliers(tables.get(role_map.get("suppliers")) if role_map.get("suppliers") else None)
    pos = standardize_pos(tables.get(role_map.get("purchase_orders")) if role_map.get("purchase_orders") else None)
    returns = standardize_returns(tables.get(role_map.get("returns")) if role_map.get("returns") else None)

    if inv.empty and not sales.empty:
        inv = sales.groupby(["sku","product"], as_index=False).agg(stock=("qty", lambda s: max(0, int(s.tail(30).mean()*15))), unit_cost=("cost", "mean"))
        inv["supplier_id"] = "UNKNOWN"
        inv["warehouse"] = "Unassigned"
        inv["min_order_qty"] = 1

    if suppliers.empty and not inv.empty:
        suppliers = pd.DataFrame({"supplier_id": inv["supplier_id"].fillna("UNKNOWN").unique()})
        suppliers["supplier_name"] = suppliers["supplier_id"]
        suppliers["lead_time_days"] = 10
        suppliers["lead_time_std_days"] = 3
        suppliers["on_time_rate"] = .85
        suppliers["defect_rate"] = .02
        suppliers["country"] = "Unknown"
        suppliers["payment_terms"] = "Unknown"
        suppliers["min_order_value"] = 0

    today = pd.Timestamp.today().normalize()
    if sales.empty:
        sku_stats = inv[["sku","product"]].copy()
        sku_stats["avg_daily_demand"] = 0.0
        sku_stats["std_daily_demand"] = 0.0
        sku_stats["recent_30d_qty"] = 0.0
        sku_stats["annual_demand_qty"] = 0.0
        sku_stats["annual_revenue"] = 0.0
        sku_stats["annual_profit"] = 0.0
    else:
        sales["date"] = pd.to_datetime(sales["date"], errors="coerce").dt.normalize()
        max_date = sales["date"].max()
        min_window = max_date - pd.Timedelta(days=89)
        recent = sales[sales["date"] >= min_window]
        daily = recent.groupby(["sku","product","date"], as_index=False).agg(qty=("qty","sum"), revenue=("revenue","sum"), profit=("profit","sum"))
        # Build complete daily series per SKU for better zero-demand handling.
        all_days = pd.date_range(min_window, max_date, freq="D")
        full_rows = []
        for (sku, product), g in daily.groupby(["sku","product"]):
            gg = g.set_index("date").reindex(all_days).fillna({"qty":0,"revenue":0,"profit":0})
            gg["sku"] = sku
            gg["product"] = product
            full_rows.append(gg.reset_index().rename(columns={"index":"date"}))
        full_daily = pd.concat(full_rows, ignore_index=True) if full_rows else pd.DataFrame(columns=["date","sku","product","qty","revenue","profit"])
        sku_stats = full_daily.groupby(["sku","product"], as_index=False).agg(
            avg_daily_demand=("qty","mean"),
            std_daily_demand=("qty","std"),
            recent_30d_qty=("qty", lambda s: float(s.tail(30).sum())),
            annual_demand_qty=("qty", lambda s: float(s.mean()*365)),
            annual_revenue=("revenue", lambda s: float(s.mean()*365)),
            annual_profit=("profit", lambda s: float(s.mean()*365)),
        )
        sku_stats["std_daily_demand"] = sku_stats["std_daily_demand"].fillna(0)

    sku_stats["avg_daily_demand"] *= demand_multiplier
    sku_stats["std_daily_demand"] *= demand_multiplier
    sku_stats["forecast_horizon_qty"] = sku_stats["avg_daily_demand"] * horizon_days

    base = inv.merge(sku_stats, on=["sku","product"], how="outer").fillna({"stock":0,"unit_cost":0,"supplier_id":"UNKNOWN","warehouse":"Unassigned","min_order_qty":1,"avg_daily_demand":0,"std_daily_demand":0,"forecast_horizon_qty":0,"annual_demand_qty":0,"annual_revenue":0,"annual_profit":0})
    base = base.merge(suppliers, on="supplier_id", how="left", suffixes=("", "_supplier"))
    base["lead_time_days"] = pd.to_numeric(base["lead_time_days"], errors="coerce").fillna(10) + lead_time_delay_days
    base["lead_time_std_days"] = pd.to_numeric(base["lead_time_std_days"], errors="coerce").fillna(3)
    base["on_time_rate"] = pd.to_numeric(base["on_time_rate"], errors="coerce").fillna(.85)
    base["defect_rate"] = pd.to_numeric(base["defect_rate"], errors="coerce").fillna(.02)
    z = z_for_service(service_level)
    base["safety_stock"] = z * base["std_daily_demand"] * np.sqrt(base["lead_time_days"].clip(lower=1))
    base["reorder_point"] = base["avg_daily_demand"] * base["lead_time_days"] + base["safety_stock"]

    open_pos = pos[~pos["status"].isin(["closed","cancelled","received","complete","completed"])] if not pos.empty else pos
    if not open_pos.empty:
        incoming = open_pos.groupby("sku", as_index=False).agg(incoming_qty=("ordered_qty","sum"), next_eta=("expected_date","min"))
    else:
        incoming = pd.DataFrame(columns=["sku","incoming_qty","next_eta"])
    base = base.merge(incoming, on="sku", how="left")
    base["incoming_qty"] = base["incoming_qty"].fillna(0)
    base["days_of_cover"] = np.where(base["avg_daily_demand"] > 0, base["stock"] / base["avg_daily_demand"], np.inf)
    base["net_position"] = base["stock"] + base["incoming_qty"]
    base["shortage_qty"] = (base["reorder_point"] - base["net_position"]).clip(lower=0)

    annual_demand = base["annual_demand_qty"].clip(lower=0)
    unit_cost = base["unit_cost"].replace(0, np.nan).fillna(1)
    annual_holding = (holding_cost_rate * unit_cost).clip(lower=0.01)
    base["eoq"] = np.sqrt((2 * annual_demand * max(order_cost, 0.01)) / annual_holding).replace([np.inf, -np.inf], 0).fillna(0)
    base["recommended_order_qty"] = np.maximum(base["shortage_qty"], base["eoq"] * (base["shortage_qty"] > 0)).round(0)
    base["recommended_order_qty"] = np.maximum(base["recommended_order_qty"], np.where(base["shortage_qty"] > 0, base["min_order_qty"], 0)).round(0)
    base["inventory_value"] = base["stock"] * base["unit_cost"]
    base["recommended_order_value"] = base["recommended_order_qty"] * base["unit_cost"]

    def risk(row):
        if row.avg_daily_demand <= 0 and row.stock > 0:
            return "Dead-stock risk"
        if row.days_of_cover <= max(3, row.lead_time_days * .35):
            return "Critical"
        if row.net_position < row.reorder_point:
            return "High"
        if row.days_of_cover <= row.lead_time_days + 7:
            return "Medium"
        return "Low"
    base["stockout_risk"] = base.apply(risk, axis=1)
    base["dead_stock_flag"] = (base["avg_daily_demand"] < 0.2) & (base["stock"] > 0)
    base["overstock_flag"] = (base["days_of_cover"] > 90) & (base["stock"] > 0)

    base = base.sort_values("annual_revenue", ascending=False)
    total_rev = base["annual_revenue"].sum()
    if total_rev > 0:
        base["cum_revenue_pct"] = base["annual_revenue"].cumsum() / total_rev
        base["abc_class"] = np.select([base["cum_revenue_pct"] <= .80, base["cum_revenue_pct"] <= .95], ["A", "B"], default="C")
    else:
        base["cum_revenue_pct"] = 0
        base["abc_class"] = "C"

    # Supplier risk.
    supplier_sku = base.groupby("supplier_id", as_index=False).agg(
        supplier_inventory_value=("inventory_value","sum"),
        supplier_skus=("sku","nunique"),
        avg_lead_time=("lead_time_days","mean"),
        avg_lead_time_std=("lead_time_std_days","mean"),
        avg_on_time_rate=("on_time_rate","mean"),
        avg_defect_rate=("defect_rate","mean"),
        critical_skus=("stockout_risk", lambda s: int((s=="Critical").sum())),
        high_risk_skus=("stockout_risk", lambda s: int(s.isin(["Critical","High"]).sum())),
        recommended_order_value=("recommended_order_value","sum"),
    )
    supplier_sku["supplier_risk_score"] = (
        (1 - supplier_sku["avg_on_time_rate"].clip(0,1)) * 45
        + supplier_sku["avg_defect_rate"].clip(0,1) * 250
        + supplier_sku["avg_lead_time"].clip(0,60) / 60 * 25
        + supplier_sku["avg_lead_time_std"].clip(0,20) / 20 * 15
        + np.minimum(supplier_sku["high_risk_skus"], 5) * 3
    ).clip(0,100).round(1)
    supplier_details = suppliers[["supplier_id","supplier_name","country","payment_terms","min_order_value"]].drop_duplicates("supplier_id") if not suppliers.empty else pd.DataFrame(columns=["supplier_id","supplier_name","country","payment_terms","min_order_value"])
    supplier_risk = supplier_sku.merge(supplier_details, on="supplier_id", how="left")
    supplier_risk["risk_level"] = pd.cut(supplier_risk["supplier_risk_score"], bins=[-1,25,50,75,100], labels=["Low","Medium","High","Critical"]).astype(str)
    supplier_risk = supplier_risk.sort_values("supplier_risk_score", ascending=False)

    # Demand anomalies.
    anomalies = []
    if not sales.empty:
        daily_sku = sales.groupby(["sku","product","date"], as_index=False).agg(qty=("qty","sum"), revenue=("revenue","sum"))
        for sku, g in daily_sku.groupby("sku"):
            if len(g) < 10:
                continue
            q1, q3 = g["qty"].quantile([.25,.75])
            iqr = q3-q1
            upper = q3 + 1.5*iqr
            hits = g[g["qty"] > max(upper, g["qty"].mean()+2*g["qty"].std())]
            for _, r in hits.tail(5).iterrows():
                anomalies.append({"sku": r["sku"], "product": r["product"], "date": str(r["date"].date()), "metric": "demand_spike", "value": float(r["qty"]), "expected_upper": float(max(upper, 0)), "severity": "Medium" if r["qty"] < upper*1.8 else "High"})
    anomalies_df = pd.DataFrame(anomalies).sort_values(["severity","value"], ascending=[True, False]) if anomalies else pd.DataFrame(columns=["sku","product","date","metric","value","expected_upper","severity"])

    reorder_plan = base[base["recommended_order_qty"] > 0].copy().sort_values(["stockout_risk","recommended_order_value"], ascending=[True, False])
    reorder_cols = ["sku","product","supplier_id","supplier_name","stock","incoming_qty","avg_daily_demand","days_of_cover","lead_time_days","safety_stock","reorder_point","recommended_order_qty","recommended_order_value","stockout_risk","abc_class"]
    reorder_plan = reorder_plan[[c for c in reorder_cols if c in reorder_plan.columns]]

    alerts = []
    for _, r in base[base["stockout_risk"].isin(["Critical","High"])].head(40).iterrows():
        alerts.append({"type":"stockout_risk", "priority": "P1" if r["stockout_risk"]=="Critical" else "P2", "sku": r["sku"], "message": f"{r['product']} has {r['stockout_risk']} stockout risk with {r['days_of_cover']:.1f} days of cover.", "recommended_action": f"Order {int(r['recommended_order_qty'])} units from {r.get('supplier_name', r['supplier_id'])}."})
    for _, r in supplier_risk[supplier_risk["risk_level"].isin(["High","Critical"])].head(20).iterrows():
        alerts.append({"type":"supplier_risk", "priority": "P1" if r["risk_level"]=="Critical" else "P2", "supplier_id": r["supplier_id"], "message": f"Supplier {r.get('supplier_name', r['supplier_id'])} has {r['risk_level']} risk score {r['supplier_risk_score']}.", "recommended_action": "Review alternate suppliers, open PO ETAs, and quality issues before new large orders."})
    for _, r in base[base["dead_stock_flag"]].head(20).iterrows():
        alerts.append({"type":"dead_stock", "priority":"P3", "sku": r["sku"], "message": f"{r['product']} has stock but almost no recent demand.", "recommended_action":"Consider markdown, bundle, ad campaign, or stop replenishment."})

    automation_playbooks = [
        {"name":"Daily stockout watch", "trigger":"Every day 08:30", "condition":"stockout_risk in Critical or High", "action":"Create reorder task + send procurement draft for approval", "approval_required": True},
        {"name":"Supplier delay watch", "trigger":"Every 4 hours", "condition":"open PO expected date breached or supplier risk > 75", "action":"Notify operations owner and request ETA update", "approval_required": False},
        {"name":"Dead-stock cleanup", "trigger":"Weekly Monday", "condition":"days_of_cover > 90 or avg_daily_demand < 0.2", "action":"Create markdown/bundling candidate list", "approval_required": True},
        {"name":"Demand spike watch", "trigger":"Daily after sales sync", "condition":"IQR demand anomaly detected", "action":"Check promo/calendar cause and recalculate reorder plan", "approval_required": False},
        {"name":"Budget guardrail", "trigger":"Before PO approval", "condition":"recommended_order_value exceeds monthly budget threshold", "action":"Route to finance approval", "approval_required": True},
    ]

    kpis = {
        "total_inventory_value": float(base["inventory_value"].sum()),
        "recommended_order_value": float(reorder_plan["recommended_order_value"].sum()) if not reorder_plan.empty and "recommended_order_value" in reorder_plan else 0.0,
        "critical_skus": int((base["stockout_risk"] == "Critical").sum()),
        "high_risk_skus": int(base["stockout_risk"].isin(["Critical","High"]).sum()),
        "dead_stock_skus": int(base["dead_stock_flag"].sum()),
        "overstock_skus": int(base["overstock_flag"].sum()),
        "supplier_high_risk": int(supplier_risk["risk_level"].isin(["Critical","High"]).sum()) if not supplier_risk.empty else 0,
        "forecast_horizon_days": horizon_days,
        "service_level": service_level,
    }

    return {
        "sales": sales,
        "inventory": inv,
        "suppliers": suppliers,
        "purchase_orders": pos,
        "returns": returns,
        "inventory_health": base.sort_values(["stockout_risk","inventory_value"], ascending=[True, False]),
        "reorder_plan": reorder_plan,
        "supplier_risk": supplier_risk,
        "anomalies": anomalies_df,
        "alerts": alerts,
        "automation_playbooks": automation_playbooks,
        "kpis": kpis,
        "params": {"horizon_days": horizon_days, "service_level": service_level, "order_cost": order_cost, "holding_cost_rate": holding_cost_rate, "demand_multiplier": demand_multiplier, "lead_time_delay_days": lead_time_delay_days},
    }


def make_report(model: Dict, ai_text: str = "") -> str:
    k = model["kpis"]
    top_reorders = model["reorder_plan"].head(10)
    supplier_risk = model["supplier_risk"].head(8)
    lines = [
        "# SupplyChainOps AI Executive Report",
        "",
        "## Executive Summary",
        f"- Inventory value under review: **{k['total_inventory_value']:,.2f}**.",
        f"- Recommended reorder value: **{k['recommended_order_value']:,.2f}**.",
        f"- Critical SKUs: **{k['critical_skus']}**.",
        f"- High/Critical stockout SKUs: **{k['high_risk_skus']}**.",
        f"- Dead-stock candidates: **{k['dead_stock_skus']}**.",
        f"- High-risk suppliers: **{k['supplier_high_risk']}**.",
        "",
    ]
    if ai_text:
        lines += ["## AI Operations Narrative", ai_text.strip(), ""]
    lines += ["## Top Reorder Recommendations"]
    if top_reorders.empty:
        lines.append("No reorder recommendations were generated.")
    else:
        for _, r in top_reorders.iterrows():
            lines.append(f"- **{r.get('sku')} / {r.get('product')}**: order **{int(r.get('recommended_order_qty',0))}** units; risk: **{r.get('stockout_risk')}**; estimated value: **{float(r.get('recommended_order_value',0)):,.2f}**.")
    lines += ["", "## Supplier Risk Watchlist"]
    if supplier_risk.empty:
        lines.append("No supplier risk data available.")
    else:
        for _, r in supplier_risk.iterrows():
            lines.append(f"- **{r.get('supplier_name', r.get('supplier_id'))}**: risk score **{r.get('supplier_risk_score')}** ({r.get('risk_level')}); high-risk SKUs: **{r.get('high_risk_skus')}**.")
    lines += ["", "## Recommended Operating Actions"]
    for alert in model["alerts"][:15]:
        lines.append(f"- **{alert.get('priority')} / {alert.get('type')}**: {alert.get('message')} Action: {alert.get('recommended_action')}")
    lines += ["", "## Governance Notes", "- Treat recommendations as decision support, not automatic purchase approval.", "- Review supplier contracts, cash limits, lead-time assumptions, and current open POs before placing orders.", "- Use approval gates for procurement emails, PO creation, and budget-impacting changes."]
    return "\n".join(lines)


def model_to_jsonable(model: Dict) -> Dict:
    out = {"kpis": model.get("kpis", {}), "params": model.get("params", {}), "alerts": model.get("alerts", []), "automation_playbooks": model.get("automation_playbooks", [])}
    for key in ["inventory_health","reorder_plan","supplier_risk","anomalies"]:
        df = model.get(key)
        if isinstance(df, pd.DataFrame):
            safe = df.copy()
            for col in safe.columns:
                if pd.api.types.is_datetime64_any_dtype(safe[col]):
                    safe[col] = safe[col].astype(str)
            out[key] = safe.head(500).replace([np.inf, -np.inf], None).where(pd.notnull(safe), None).to_dict(orient="records")
    return out


def procurement_email_draft(reorder_plan: pd.DataFrame, supplier_id: str | None = None) -> str:
    df = reorder_plan.copy()
    if supplier_id and supplier_id != "All suppliers":
        df = df[df["supplier_id"].astype(str) == str(supplier_id)]
    if df.empty:
        return "Subject: Reorder Review\n\nHi team,\n\nNo reorder items are currently flagged for this supplier.\n\nRegards,\nOperations"
    total = df.get("recommended_order_value", pd.Series(dtype=float)).sum()
    lines = ["Subject: Reorder Approval Request", "", "Hi team,", "", "Please review the following reorder recommendations before purchase approval:", ""]
    for _, r in df.head(20).iterrows():
        lines.append(f"- {r.get('sku')} / {r.get('product')}: {int(r.get('recommended_order_qty',0))} units, risk {r.get('stockout_risk')}, estimated value {float(r.get('recommended_order_value',0)):,.2f}")
    lines += ["", f"Estimated order value: {total:,.2f}", "", "Please confirm budget, supplier ETA, and any open purchase orders before releasing this order.", "", "Regards,", "SupplyChainOps AI"]
    return "\n".join(lines)

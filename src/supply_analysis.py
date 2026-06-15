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
    if any(x in text for x in ["bom", "bill_of_materials", "recipe", "component_map", "parent_sku"]):
        return "bom"
    if any(x in text for x in ["purchase_order", "po_id", "ordered_qty", "expected_date"]):
        return "purchase_orders"
    if any(x in text for x in ["stock_on_hand", "inventory", "warehouse", "reorder", "stock_quantity"]):
        return "inventory"
    if any(x in text for x in ["supplier", "vendor", "lead_time", "defect_rate", "on_time"]):
        return "suppliers"
    if any(x in text for x in ["return", "refund", "return_qty"]):
        return "returns"
    if any(x in text for x in ["sales", "order_date", "quantity_sold", "revenue", "profit"]):
        return "sales"
    return "other"


def pick_tables(tables: Dict[str, pd.DataFrame]) -> Dict[str, str | None]:
    roles = {"sales": None, "inventory": None, "suppliers": None, "purchase_orders": None, "returns": None, "bom": None}
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
        return pd.DataFrame(columns=["sku","product","stock","unit_cost","supplier_id","warehouse","min_order_qty","storage_class"])
    d = df.copy()
    sku = _find_col(d, ["sku","product_id","item_id","item_code","product_code"])
    product = _find_col(d, ["product","product_name","item","item_name","name"])
    stock = _find_col(d, ["stock_on_hand","stock","inventory","stock_quantity","qty_on_hand","available_qty"])
    unit_cost = _find_col(d, ["unit_cost","cost","purchase_cost","standard_cost"])
    supplier = _find_col(d, ["supplier_id","vendor_id","supplier","vendor"])
    warehouse = _find_col(d, ["warehouse","location","dc","fulfillment_center"])
    moq = _find_col(d, ["min_order_qty","moq","minimum_order_quantity"])
    storage_class = _find_col(d, ["storage_class", "class", "storage_type"])
    out = pd.DataFrame()
    out["sku"] = d[sku].astype(str) if sku else d.index.astype(str)
    out["product"] = d[product].astype(str) if product else out["sku"]
    out["stock"] = pd.to_numeric(d[stock], errors="coerce").fillna(0) if stock else 0
    out["unit_cost"] = pd.to_numeric(d[unit_cost], errors="coerce").fillna(0) if unit_cost else 0
    out["supplier_id"] = d[supplier].astype(str) if supplier else "UNKNOWN"
    out["warehouse"] = d[warehouse].astype(str) if warehouse else "Unassigned"
    out["min_order_qty"] = pd.to_numeric(d[moq], errors="coerce").fillna(1) if moq else 1
    out["storage_class"] = d[storage_class].astype(str).str.lower() if storage_class else "standard"
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


def standardize_bom(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["parent_sku","component_sku","component_name","qty_required"])
    d = df.copy()
    parent = _find_col(d, ["parent_sku", "parent", "finished_sku", "sku"])
    comp = _find_col(d, ["component_sku", "component", "child_sku"])
    name = _find_col(d, ["component_name", "name", "component_title", "title"])
    qty = _find_col(d, ["qty_required", "quantity", "qty", "units_required"])
    
    out = pd.DataFrame()
    out["parent_sku"] = d[parent].astype(str) if parent else "UNKNOWN"
    out["component_sku"] = d[comp].astype(str) if comp else "UNKNOWN"
    out["component_name"] = d[name].astype(str) if name else out["component_sku"]
    out["qty_required"] = pd.to_numeric(d[qty], errors="coerce").fillna(1.0) if qty else 1.0
    return out


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
    bom = standardize_bom(tables.get(role_map.get("bom")) if role_map.get("bom") else None)

    # Generate mock BOM recipes if bom is empty (and sample data is used)
    is_mock_bom = False
    if bom.empty and not inv.empty:
        is_mock_bom = True
        mock_bom_data = [
            {"parent_sku": "SKU-001", "component_sku": "COMP-001", "component_name": "Premium Glass Bottle", "qty_required": 1.0},
            {"parent_sku": "SKU-001", "component_sku": "COMP-002", "component_name": "Leakproof Cap w/ Seal", "qty_required": 1.0},
            {"parent_sku": "SKU-001", "component_sku": "COMP-003", "component_name": "Silicone Straw & Cap Attachment", "qty_required": 1.0},
            
            {"parent_sku": "SKU-002", "component_sku": "COMP-004", "component_name": "Foil Protein Bar Wrapper", "qty_required": 12.0},
            {"parent_sku": "SKU-002", "component_sku": "COMP-005", "component_name": "Corrugated Display Carton Box", "qty_required": 1.0},
            
            {"parent_sku": "SKU-003", "component_sku": "COMP-006", "component_name": "Nylon Mat Carrying Strap", "qty_required": 1.0},
            {"parent_sku": "SKU-003", "component_sku": "COMP-007", "component_name": "Eco-friendly TPE Mat Roll (Purple)", "qty_required": 1.0},
        ]
        bom = pd.DataFrame(mock_bom_data)

    if inv.empty and not sales.empty:
        inv = sales.groupby(["sku","product"], as_index=False).agg(stock=("qty", lambda s: max(0, int(s.tail(30).mean()*15))), unit_cost=("cost", "mean"))
        inv["supplier_id"] = "UNKNOWN"
        inv["warehouse"] = "Unassigned"
        inv["min_order_qty"] = 1
        inv["storage_class"] = "standard"

    if is_mock_bom and not inv.empty:
        mock_comp_rows = [
            {"sku": "COMP-001", "product": "Premium Glass Bottle", "stock": 45, "unit_cost": 1.20, "supplier_id": "SUP-01", "warehouse": "Bengaluru DC", "min_order_qty": 500, "storage_class": "fragile"},
            {"sku": "COMP-002", "product": "Leakproof Cap w/ Seal", "stock": 120, "unit_cost": 0.30, "supplier_id": "SUP-01", "warehouse": "Bengaluru DC", "min_order_qty": 1000, "storage_class": "standard"},
            {"sku": "COMP-003", "product": "Silicone Straw & Cap Attachment", "stock": 15, "unit_cost": 0.45, "supplier_id": "SUP-03", "warehouse": "Bengaluru DC", "min_order_qty": 500, "storage_class": "standard"},
            {"sku": "COMP-004", "product": "Foil Protein Bar Wrapper", "stock": 2500, "unit_cost": 0.08, "supplier_id": "SUP-02", "warehouse": "Mumbai DC", "min_order_qty": 10000, "storage_class": "standard"},
            {"sku": "COMP-005", "product": "Corrugated Display Carton Box", "stock": 80, "unit_cost": 0.50, "supplier_id": "SUP-02", "warehouse": "Mumbai DC", "min_order_qty": 1000, "storage_class": "standard"},
            {"sku": "COMP-006", "product": "Nylon Mat Carrying Strap", "stock": 35, "unit_cost": 0.80, "supplier_id": "SUP-03", "warehouse": "Mumbai DC", "min_order_qty": 500, "storage_class": "standard"},
            {"sku": "COMP-007", "product": "Eco-friendly TPE Mat Roll (Purple)", "stock": 8, "unit_cost": 4.50, "supplier_id": "SUP-03", "warehouse": "Mumbai DC", "min_order_qty": 200, "storage_class": "cold-chain"},
        ]
        mock_comp_df = pd.DataFrame(mock_comp_rows)
        existing_skus = set(inv["sku"].unique())
        mock_comp_df = mock_comp_df[~mock_comp_df["sku"].isin(existing_skus)]
        if not mock_comp_df.empty:
            inv = pd.concat([inv, mock_comp_df], ignore_index=True)

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

    base = inv.merge(sku_stats, on=["sku","product"], how="outer").fillna({"stock":0,"unit_cost":0,"supplier_id":"UNKNOWN","warehouse":"Unassigned","min_order_qty":1,"storage_class":"standard","avg_daily_demand":0,"std_daily_demand":0,"forecast_horizon_qty":0,"annual_demand_qty":0,"annual_revenue":0,"annual_profit":0})
    
    # Calculate dependent demand for components
    base["is_component"] = base["sku"].isin(bom["component_sku"])
    base["component_avg_daily_demand"] = 0.0
    base["component_forecast_qty"] = 0.0
    base["component_annual_demand"] = 0.0
    base["component_std_daily_demand"] = 0.0
    
    if not bom.empty:
        for comp_sku, comp_group in bom.groupby("component_sku"):
            dep_avg_demand = 0.0
            dep_forecast_qty = 0.0
            dep_annual_demand = 0.0
            dep_std_demand = 0.0
            for _, r_bom in comp_group.iterrows():
                parent_sku = r_bom["parent_sku"]
                qty_req = r_bom["qty_required"]
                parent_rows = base[base["sku"] == parent_sku]
                if not parent_rows.empty:
                    dep_avg_demand += parent_rows["avg_daily_demand"].sum() * qty_req
                    dep_forecast_qty += parent_rows["forecast_horizon_qty"].sum() * qty_req
                    dep_annual_demand += parent_rows["annual_demand_qty"].sum() * qty_req
                    dep_std_demand += parent_rows["std_daily_demand"].sum() * qty_req
            base.loc[base["sku"] == comp_sku, "component_avg_daily_demand"] = dep_avg_demand
            base.loc[base["sku"] == comp_sku, "component_forecast_qty"] = dep_forecast_qty
            base.loc[base["sku"] == comp_sku, "component_annual_demand"] = dep_annual_demand
            base.loc[base["sku"] == comp_sku, "component_std_daily_demand"] = dep_std_demand
            
        comp_mask = base["is_component"]
        base.loc[comp_mask, "avg_daily_demand"] = base.loc[comp_mask, "component_avg_daily_demand"]
        base.loc[comp_mask, "forecast_horizon_qty"] = base.loc[comp_mask, "component_forecast_qty"]
        base.loc[comp_mask, "annual_demand_qty"] = base.loc[comp_mask, "component_annual_demand"]
        base.loc[comp_mask, "std_daily_demand"] = base.loc[comp_mask, "component_std_daily_demand"]

    # Dynamic holding cost rate by storage class
    base["holding_cost_rate"] = base["storage_class"].apply(lambda sc: 0.28 if sc == "fragile" else (0.35 if sc == "cold-chain" else holding_cost_rate))

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
    annual_holding = (base["holding_cost_rate"] * unit_cost).clip(lower=0.01)
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
        avg_unit_cost=("unit_cost","mean"),
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
    ]    # Calculate returns analysis if returns data is available
    reasons_summary = []
    sku_returns_df = pd.DataFrame(columns=["sku", "product", "supplier_id", "supplier_name", "total_return_qty", "total_refund_amount", "total_sales_qty", "return_rate"])
    supplier_returns_df = pd.DataFrame(columns=["supplier_id", "supplier_name", "supplier_return_qty", "supplier_refund_amount", "supplier_quality_return_qty"])
    total_refund_value = 0.0
    total_returns_qty = 0

    if not returns.empty:
        total_refund_value = float(returns["refund_amount"].sum())
        total_returns_qty = int(returns["return_qty"].sum())
        reasons_summary_df = returns.groupby("reason", as_index=False).agg(
            return_qty=("return_qty", "sum"),
            refund_amount=("refund_amount", "sum"),
            cases=("return_qty", "count")
        )
        reasons_summary = reasons_summary_df.to_dict(orient="records")

        # SKU return rates
        sku_returns = returns.groupby("sku", as_index=False).agg(
            total_return_qty=("return_qty", "sum"),
            total_refund_amount=("refund_amount", "sum")
        )
        sku_sales = sales.groupby("sku", as_index=False).agg(total_sales_qty=("qty", "sum")) if not sales.empty else pd.DataFrame(columns=["sku", "total_sales_qty"])
        
        sku_returns_df = base[["sku", "product", "supplier_id", "supplier_name", "unit_cost"]].drop_duplicates("sku").merge(sku_returns, on="sku", how="left").fillna(0)
        sku_returns_df = sku_returns_df.merge(sku_sales, on="sku", how="left").fillna(0)
        sku_returns_df["return_rate"] = np.where(
            sku_returns_df["total_sales_qty"] > 0,
            (sku_returns_df["total_return_qty"] / sku_returns_df["total_sales_qty"]).clip(0, 1),
            0.0
        )
        
        # Supplier returns correlation
        returns_with_supplier = returns.merge(base[["sku", "supplier_id", "supplier_name"]].drop_duplicates("sku"), on="sku", how="left")
        supplier_returns_df = returns_with_supplier.groupby(["supplier_id", "supplier_name"], as_index=False).agg(
            supplier_return_qty=("return_qty", "sum"),
            supplier_refund_amount=("refund_amount", "sum")
        )
        
        # Count quality returns specifically
        quality_returns = returns_with_supplier[returns_with_supplier["reason"].isin(["quality_issue", "damaged"])]
        if not quality_returns.empty:
            supplier_quality = quality_returns.groupby("supplier_id", as_index=False).agg(supplier_quality_return_qty=("return_qty", "sum"))
            supplier_returns_df = supplier_returns_df.merge(supplier_quality, on="supplier_id", how="left").fillna(0)
        else:
            supplier_returns_df["supplier_quality_return_qty"] = 0
        supplier_returns_df["supplier_quality_return_qty"] = supplier_returns_df["supplier_quality_return_qty"].astype(int)

    # Inter-DC Inventory Transfers Recommendation
    transfers = []
    saved_transfer_value = 0.0
    if "warehouse" in base.columns and base["warehouse"].nunique() > 1:
        # We find deficit and surplus by SKU
        for sku, group in base.groupby("sku"):
            if len(group) < 2:
                continue
            deficits = []
            surpluses = []
            for _, row in group.iterrows():
                ss = row.get("safety_stock", 0)
                rop = row.get("reorder_point", 0)
                stock = row.get("stock", 0)
                wh = row.get("warehouse", "Unassigned")
                
                if stock < ss:
                    deficits.append({"warehouse": wh, "qty": ss - stock, "row": row})
                elif stock > rop:
                    surpluses.append({"warehouse": wh, "qty": stock - rop, "row": row})
            
            # Match deficit and surplus
            for def_item in deficits:
                for sur_item in surpluses:
                    if def_item["qty"] <= 0 or sur_item["qty"] <= 0:
                        continue
                    transfer_qty = min(def_item["qty"], sur_item["qty"])
                    if transfer_qty >= 1:
                        transfers.append({
                            "sku": sku,
                            "product": def_item["row"].get("product", sku),
                            "from_warehouse": sur_item["warehouse"],
                            "to_warehouse": def_item["warehouse"],
                            "qty": int(round(transfer_qty)),
                            "unit_cost": float(def_item["row"].get("unit_cost", 0)),
                            "saved_value": float(transfer_qty * def_item["row"].get("unit_cost", 0))
                        })
                        def_item["qty"] -= transfer_qty
                        sur_item["qty"] -= transfer_qty
        
        if transfers:
            saved_transfer_value = sum(t["saved_value"] for t in transfers)
            # Add an alert if there are transfers
            alerts.append({
                "type": "warehouse_transfer",
                "priority": "P3",
                "sku": "Multiple",
                "message": f"Found {len(transfers)} internal stock transfer opportunities to reduce purchasing cost by {saved_transfer_value:,.2f}.",
                "recommended_action": "Review the Inter-DC Transfer Advisor tab to approve internal inventory routing."
            })

    # Cost / service level optimization curves
    service_levels = [0.80, 0.85, 0.90, 0.95, 0.98, 0.99]
    cost_curves = []
    # We will compute carrying costs vs stockout penalties under standard penalty factor (1.5x of unit cost/margin)
    for sl in service_levels:
        z_score = z_for_service(sl)
        total_carrying = 0.0
        total_stockout = 0.0
        for _, row in base.iterrows():
            std_demand = row.get("std_daily_demand", 0)
            lead_time = row.get("lead_time_days", 10)
            unit_cost = row.get("unit_cost", 0)
            annual_demand = row.get("annual_demand_qty", 0)
            
            ss = z_score * std_demand * np.sqrt(max(1, lead_time))
            carrying = ss * unit_cost * holding_cost_rate
            
            # Approximated penalty is 1.5 times the unit cost
            penalty = max(1.0, unit_cost * 1.5)
            shortage = (1 - sl) * annual_demand
            stockout = shortage * penalty
            
            total_carrying += carrying
            total_stockout += stockout
            
        cost_curves.append({
            "service_level": sl,
            "carrying_cost": float(total_carrying),
            "stockout_cost": float(total_stockout),
            "total_cost": float(total_carrying + total_stockout)
        })

    # Freight Mode Optimizer calculations (Air vs Ocean)
    freight_df = pd.DataFrame()
    freight_df["sku"] = base["sku"]
    freight_df["product"] = base["product"]
    freight_df["annual_demand"] = base["annual_demand_qty"].clip(lower=0)
    freight_df["unit_cost"] = base["unit_cost"]
    
    lead_time_ocean = base["lead_time_days"].clip(lower=1)
    lead_time_air = np.maximum(3.0, base["lead_time_days"] * 0.25).round(1)
    freight_df["lead_time_ocean"] = lead_time_ocean
    freight_df["lead_time_air"] = lead_time_air
    
    freight_cost_ocean_unit = (base["unit_cost"] * 0.08 + 0.50).round(2)
    freight_cost_air_unit = (base["unit_cost"] * 0.30 + 4.00).round(2)
    freight_df["freight_cost_ocean_unit"] = freight_cost_ocean_unit
    freight_df["freight_cost_air_unit"] = freight_cost_air_unit
    
    freight_df["annual_freight_ocean"] = freight_df["annual_demand"] * freight_cost_ocean_unit
    freight_df["annual_freight_air"] = freight_df["annual_demand"] * freight_cost_air_unit
    
    z = z_for_service(service_level)
    ss_ocean = z * base["std_daily_demand"] * np.sqrt(lead_time_ocean)
    ss_air = z * base["std_daily_demand"] * np.sqrt(lead_time_air)
    
    freight_df["carrying_cost_ocean"] = ss_ocean * base["unit_cost"] * base["holding_cost_rate"]
    freight_df["carrying_cost_air"] = ss_air * base["unit_cost"] * base["holding_cost_rate"]
    
    freight_df["pipeline_cost_ocean"] = (freight_df["annual_demand"] * base["unit_cost"] * base["holding_cost_rate"] * (lead_time_ocean / 365.0))
    freight_df["pipeline_cost_air"] = (freight_df["annual_demand"] * base["unit_cost"] * base["holding_cost_rate"] * (lead_time_air / 365.0))
    
    freight_df["total_cost_ocean"] = freight_df["annual_freight_ocean"] + freight_df["carrying_cost_ocean"] + freight_df["pipeline_cost_ocean"]
    freight_df["total_cost_air"] = freight_df["annual_freight_air"] + freight_df["carrying_cost_air"] + freight_df["pipeline_cost_air"]
    
    freight_df["recommended_mode"] = np.where(freight_df["total_cost_air"] < freight_df["total_cost_ocean"], "Air", "Ocean")
    freight_df["cost_difference"] = np.abs(freight_df["total_cost_air"] - freight_df["total_cost_ocean"])

    # Financial health & velocity dashboard calculations (DIO, Turnover, carrying costs)
    fin_df = pd.DataFrame()
    fin_df["sku"] = base["sku"]
    fin_df["product"] = base["product"]
    fin_df["storage_class"] = base["storage_class"]
    fin_df["annual_cogs"] = (base["annual_demand_qty"] * base["unit_cost"]).clip(lower=0)
    
    avg_inv_qty = np.maximum(base["safety_stock"] + (base["eoq"] / 2.0), base["stock"])
    fin_df["average_inventory_value"] = (avg_inv_qty * base["unit_cost"]).clip(lower=0)
    
    fin_df["itr"] = np.where(
        fin_df["average_inventory_value"] > 0,
        fin_df["annual_cogs"] / fin_df["average_inventory_value"],
        0.0
    )
    fin_df["dio"] = np.where(
        fin_df["itr"] > 0,
        365.0 / fin_df["itr"],
        365.0
    )
    fin_df["dio"] = np.minimum(fin_df["dio"], 365.0)
    fin_df["annual_carrying_cost"] = fin_df["average_inventory_value"] * base["holding_cost_rate"]

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
        "total_refund_value": total_refund_value,
        "total_returns_qty": total_returns_qty,
        "saved_transfer_value": saved_transfer_value,
        "transfers_count": len(transfers),
        "total_annual_cogs": float(fin_df["annual_cogs"].sum()),
        "total_avg_inventory_value": float(fin_df["average_inventory_value"].sum()),
        "portfolio_itr": float(fin_df["annual_cogs"].sum() / fin_df["average_inventory_value"].sum()) if fin_df["average_inventory_value"].sum() > 0 else 0.0,
        "portfolio_dio": float(365.0 * fin_df["average_inventory_value"].sum() / fin_df["annual_cogs"].sum()) if fin_df["annual_cogs"].sum() > 0 else 365.0,
        "total_annual_carrying_cost": float(fin_df["annual_carrying_cost"].sum()),
    }

    return {
        "sales": sales,
        "inventory": inv,
        "suppliers": suppliers,
        "purchase_orders": pos,
        "returns": returns,
        "bom": bom,
        "freight_comparisons": freight_df,
        "financial_kpis": fin_df,
        "inventory_health": base.sort_values(["stockout_risk","inventory_value"], ascending=[True, False]),
        "reorder_plan": reorder_plan,
        "supplier_risk": supplier_risk,
        "anomalies": anomalies_df,
        "alerts": alerts,
        "automation_playbooks": automation_playbooks,
        "kpis": kpis,
        "returns_by_reason": reasons_summary,
        "sku_returns": sku_returns_df,
        "supplier_returns": supplier_returns_df,
        "transfers": pd.DataFrame(transfers) if transfers else pd.DataFrame(columns=["sku", "product", "from_warehouse", "to_warehouse", "qty", "unit_cost", "saved_value"]),
        "cost_curves": cost_curves,
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
    out = {
        "kpis": model.get("kpis", {}),
        "params": model.get("params", {}),
        "alerts": model.get("alerts", []),
        "automation_playbooks": model.get("automation_playbooks", []),
        "returns_by_reason": model.get("returns_by_reason", []),
        "cost_curves": model.get("cost_curves", []),
    }
    for key in ["inventory_health","reorder_plan","supplier_risk","anomalies","sku_returns","supplier_returns","transfers","bom","freight_comparisons","financial_kpis"]:
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


def score_suppliers_mcda(supplier_risk_df: pd.DataFrame, w_price: float, w_speed: float, w_reliability: float, w_quality: float) -> pd.DataFrame:
    if supplier_risk_df.empty:
        return pd.DataFrame()
    
    df = supplier_risk_df.copy()
    if "avg_unit_cost" not in df.columns:
        df["avg_unit_cost"] = 10.0
        
    # Price (Lower is better)
    max_p = df["avg_unit_cost"].max()
    min_p = df["avg_unit_cost"].min()
    if max_p != min_p:
        df["score_price"] = 100 * (max_p - df["avg_unit_cost"]) / (max_p - min_p)
    else:
        df["score_price"] = 100.0
        
    # Speed/Lead Time (Lower is better)
    max_lt = df["avg_lead_time"].max()
    min_lt = df["avg_lead_time"].min()
    if max_lt != min_lt:
        df["score_speed"] = 100 * (max_lt - df["avg_lead_time"]) / (max_lt - min_lt)
    else:
        df["score_speed"] = 100.0
        
    # Reliability/On-time Rate (Higher is better)
    df["score_reliability"] = df["avg_on_time_rate"] * 100
    
    # Quality/Defect Rate (Lower is better)
    df["score_quality"] = (1.0 - df["avg_defect_rate"]) * 100
    
    # Calculate weighted MCDA score
    total_w = w_price + w_speed + w_reliability + w_quality
    if total_w <= 0:
        total_w = 1.0
        
    df["mcda_score"] = (
        w_price * df["score_price"] +
        w_speed * df["score_speed"] +
        w_reliability * df["score_reliability"] +
        w_quality * df["score_quality"]
    ) / total_w
    
    return df.round(2)


def generate_rfq_draft(supplier_name: str, sku: str, product_name: str, qty: int, target_price: float, expected_delivery: str) -> str:
    lines = [
        f"Subject: Request for Quote (RFQ) - {product_name} ({sku})",
        "",
        f"Dear {supplier_name} Team,",
        "",
        f"We would like to request a formal quotation for the purchase of the following items:",
        "",
        f"- Product Name: {product_name}",
        f"- SKU: {sku}",
        f"- Order Quantity: {qty:,} units",
        f"- Target Unit Price: ${target_price:,.2f}" if target_price > 0 else f"- Target Unit Price: Competitive Market Rate",
        f"- Requested Delivery Date: {expected_delivery}",
        "",
        "Please confirm your capacity to supply this quantity, your standard lead time, payment terms, and total pricing including shipping terms (FOB/DDP).",
        "",
        "We look forward to your prompt response.",
        "",
        "Best regards,",
        "Procurement Team",
        "SupplyChainOps AI System"
    ]
    return "\n".join(lines)

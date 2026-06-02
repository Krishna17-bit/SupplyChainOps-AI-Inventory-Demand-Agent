from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ai_client import AIReasoningClient
from src.data_loader import env_db_url, load_sample_tables, load_sqlalchemy_tables, load_sqlite_path, load_uploaded_tables
from src.export_utils import df_to_csv_bytes, make_automation_json, make_excel_workbook
from src.supply_analysis import build_supply_model, make_report, model_to_jsonable, pick_tables, procurement_email_draft
from src.ui_styles import APP_CSS

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="SupplyChainOps AI",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)


def render_dark_table(df: pd.DataFrame, height: int = 360) -> None:
    if df is None or df.empty:
        st.info("No rows to display.")
        return
    safe = df.copy().head(500)
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].astype(str)
        safe[col] = safe[col].replace([np.inf, -np.inf], "∞")
    html = safe.to_html(index=False, escape=True)
    st.markdown(f"<div class='dark-table-scroll' style='max-height:{height}px'>{html}</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>{label}</div>
            <div class='metric-value'>{value}</div>
            <div class='metric-note'>{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def money(x: float) -> str:
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return "0"


client = AIReasoningClient()

with st.sidebar:
    st.markdown("### SupplyChainOps AI")
    st.markdown("<span class='small-muted'>Demand forecasting, inventory optimization, procurement planning, supplier risk, database connectors, and automation playbooks.</span>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Connection status**")
    if client.configured:
        st.success("AI narrative enabled")
    else:
        st.warning("Local analytics mode")
    st.caption(client.status_help)
    st.divider()
    horizon_days = st.slider("Forecast horizon", 7, 120, 30, step=7)
    service_level = st.selectbox("Target service level", [0.85, 0.90, 0.95, 0.98, 0.99], index=2, format_func=lambda x: f"{int(x*100)}%")
    order_cost = st.number_input("Estimated order cost", min_value=1.0, max_value=10000.0, value=35.0, step=5.0)
    holding_cost_rate = st.slider("Annual holding cost rate", 0.05, 0.80, 0.22, step=0.01)
    st.divider()
    st.markdown("**What-if scenario**")
    demand_multiplier = st.slider("Demand multiplier", 0.50, 2.50, 1.00, step=0.05)
    lead_time_delay = st.slider("Supplier delay days", 0, 45, 0, step=1)
    st.divider()
    st.markdown("**Automation guardrails**")
    webhook_url = st.text_input("Webhook URL placeholder", placeholder="https://hooks.example.com/supply-alerts")
    st.caption("The app generates automation payloads and draft actions only. It does not auto-send purchase orders.")

st.markdown(
    """
    <div class='hero'>
        <div class='hero-title'>SupplyChainOps AI</div>
        <div class='hero-subtitle'>
            Upload sales, inventory, supplier, purchase-order, returns, or database tables to generate demand forecasts,
            reorder plans, stockout risk, supplier risk, what-if scenarios, procurement drafts, automation playbooks, and audit-ready exports.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 1. Load supply-chain data")
left, right = st.columns([1.2, 1])
with left:
    uploaded = st.file_uploader(
        "Upload CSV, Excel, JSON, SQLite, or DB files",
        type=["csv", "xlsx", "xls", "json", "sqlite", "sqlite3", "db"],
        accept_multiple_files=True,
    )
with right:
    use_sample = st.checkbox("Use included sample supply-chain dataset", value=True)
    sqlite_path = st.text_input("Optional local SQLite path", placeholder="C:/path/to/inventory.db or /home/user/inventory.sqlite")

with st.expander("Advanced: connect a personal database read-only"):
    st.markdown("Use this for local/private databases. Real credentials should live in `.env`, not in GitHub.")
    default_db_url = env_db_url()
    db_url = st.text_input("SQLAlchemy database URL", value=default_db_url, type="password", placeholder="sqlite:///local.db or postgresql+psycopg2://user:pass@host/db")
    db_tables = st.text_input("Tables to import, comma-separated", placeholder="sales_history, inventory_snapshot, suppliers, purchase_orders")
    st.caption("The connector imports selected tables with a read-only SELECT LIMIT. Postgres/MySQL require the proper optional driver installed locally.")

if "tables" not in st.session_state:
    st.session_state.tables = {}
if "role_map" not in st.session_state:
    st.session_state.role_map = {}
if "model" not in st.session_state:
    st.session_state.model = None
if "report" not in st.session_state:
    st.session_state.report = ""
if "ai_summary" not in st.session_state:
    st.session_state.ai_summary = ""

load_col, run_col = st.columns([1, 1])
with load_col:
    load_workspace = st.button("Load workspace", use_container_width=True)
with run_col:
    run_analysis = st.button("Run supply-chain analysis", use_container_width=True)

if load_workspace or run_analysis:
    tables = {}
    try:
        if use_sample:
            tables.update(load_sample_tables(BASE_DIR))
        tables.update(load_uploaded_tables(uploaded))
        if sqlite_path.strip():
            tables.update(load_sqlite_path(sqlite_path))
        if db_url.strip() and db_tables.strip():
            tables.update(load_sqlalchemy_tables(db_url, db_tables, row_limit=100000))
        st.session_state.tables = tables
        st.session_state.role_map = pick_tables(tables)
        if not tables:
            st.error("No tables loaded. Upload files, enable sample data, or configure a database connection.")
        else:
            st.success(f"Loaded {len(tables)} table(s).")
    except Exception as exc:
        st.error(f"Data loading failed safely: {exc}")

tables = st.session_state.tables
role_map = st.session_state.role_map

if tables:
    st.markdown("### Loaded tables")
    table_summary = pd.DataFrame([{"table": name, "rows": len(df), "columns": len(df.columns), "detected_role": role_map.get(next((r for r, t in role_map.items() if t == name), ""), "") } for name, df in tables.items()])
    render_dark_table(table_summary, height=220)

    with st.expander("Review or override table roles", expanded=False):
        names = [None] + list(tables.keys())
        c1, c2, c3, c4, c5 = st.columns(5)
        role_map["sales"] = c1.selectbox("Sales table", names, index=names.index(role_map.get("sales")) if role_map.get("sales") in names else 0, format_func=lambda x: "None" if x is None else x)
        role_map["inventory"] = c2.selectbox("Inventory table", names, index=names.index(role_map.get("inventory")) if role_map.get("inventory") in names else 0, format_func=lambda x: "None" if x is None else x)
        role_map["suppliers"] = c3.selectbox("Suppliers table", names, index=names.index(role_map.get("suppliers")) if role_map.get("suppliers") in names else 0, format_func=lambda x: "None" if x is None else x)
        role_map["purchase_orders"] = c4.selectbox("Purchase orders", names, index=names.index(role_map.get("purchase_orders")) if role_map.get("purchase_orders") in names else 0, format_func=lambda x: "None" if x is None else x)
        role_map["returns"] = c5.selectbox("Returns table", names, index=names.index(role_map.get("returns")) if role_map.get("returns") in names else 0, format_func=lambda x: "None" if x is None else x)
        st.session_state.role_map = role_map

if run_analysis and tables:
    with st.spinner("Running demand forecasting, inventory optimization, supplier risk, and automation planning..."):
        model = build_supply_model(
            tables,
            role_map,
            horizon_days=horizon_days,
            service_level=service_level,
            order_cost=order_cost,
            holding_cost_rate=holding_cost_rate,
            demand_multiplier=demand_multiplier,
            lead_time_delay_days=lead_time_delay,
        )
        ai_summary = ""
        if client.configured:
            prompt = f"""
You are a senior supply-chain operations analyst. Write a concise executive narrative from this JSON. Focus on stockout risk, reorder priorities, supplier risk, cash locked in inventory, dead stock, and what approvals are needed. Do not invent facts outside the JSON.

{json.dumps(model_to_jsonable(model), indent=2, default=str)[:18000]}
"""
            resp = client.generate(prompt)
            if resp.ok:
                ai_summary = resp.text
        report = make_report(model, ai_summary)
        st.session_state.model = model
        st.session_state.ai_summary = ai_summary
        st.session_state.report = report
    st.success("Supply-chain analysis complete.")

model = st.session_state.model
report = st.session_state.report

if model:
    k = model["kpis"]
    st.divider()
    st.markdown("## Command center")
    m1, m2, m3, m4 = st.columns(4)
    with m1: metric_card("Inventory value", money(k["total_inventory_value"]), "Current stock capital")
    with m2: metric_card("Reorder value", money(k["recommended_order_value"]), "Recommended approval queue")
    with m3: metric_card("Critical SKUs", str(k["critical_skus"]), "Immediate review")
    with m4: metric_card("Supplier risks", str(k["supplier_high_risk"]), "High/Critical suppliers")

    tabs = st.tabs([
        "Inventory Health", "Demand Forecast", "Stockout Risk", "Reorder Plan", "Supplier Risk",
        "What-If Simulator", "Automation Center", "Procurement Assistant", "Executive Report", "Export Center"
    ])

    with tabs[0]:
        st.markdown("### Inventory health overview")
        inv_health = model["inventory_health"].copy()
        fig_df = inv_health.replace([np.inf, -np.inf], np.nan).copy()
        if not fig_df.empty:
            fig = px.scatter(fig_df, x="days_of_cover", y="inventory_value", size="stock", color="stockout_risk", hover_data=["sku","product","abc_class"], title="Inventory value vs days of cover")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)
        render_dark_table(inv_health[[c for c in ["sku","product","stock","avg_daily_demand","days_of_cover","inventory_value","stockout_risk","dead_stock_flag","overstock_flag","abc_class"] if c in inv_health.columns]], height=420)

    with tabs[1]:
        st.markdown("### Demand forecast")
        df = model["inventory_health"].copy().replace([np.inf, -np.inf], np.nan).sort_values("forecast_horizon_qty", ascending=False)
        top = df.head(20)
        if not top.empty:
            fig = px.bar(top, x="sku", y="forecast_horizon_qty", color="stockout_risk", hover_data=["product","avg_daily_demand"], title=f"Forecast demand for next {horizon_days} days")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)
        render_dark_table(df[[c for c in ["sku","product","avg_daily_demand","std_daily_demand","forecast_horizon_qty","recent_30d_qty","annual_demand_qty","abc_class"] if c in df.columns]], height=420)

    with tabs[2]:
        st.markdown("### Stockout and overstock risk")
        risk_df = model["inventory_health"].copy().replace([np.inf, -np.inf], np.nan)
        risk_counts = risk_df["stockout_risk"].value_counts().reset_index()
        risk_counts.columns = ["risk", "count"]
        fig = px.pie(risk_counts, names="risk", values="count", title="Risk distribution")
        fig.update_layout(height=380, paper_bgcolor="#070707", font_color="#ffffff")
        st.plotly_chart(fig, use_container_width=True)
        render_dark_table(risk_df.sort_values(["stockout_risk","days_of_cover"])[[c for c in ["sku","product","stock","incoming_qty","days_of_cover","lead_time_days","reorder_point","shortage_qty","stockout_risk","supplier_name"] if c in risk_df.columns]], height=460)

    with tabs[3]:
        st.markdown("### Reorder plan")
        reorder = model["reorder_plan"]
        if reorder.empty:
            st.success("No reorder recommendations under the current scenario.")
        else:
            render_dark_table(reorder, height=500)
            fig = px.bar(reorder.head(20), x="sku", y="recommended_order_value", color="stockout_risk", hover_data=["product","recommended_order_qty"], title="Top reorder value recommendations")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)

    with tabs[4]:
        st.markdown("### Supplier risk")
        supplier_risk = model["supplier_risk"]
        render_dark_table(supplier_risk, height=460)
        if not supplier_risk.empty:
            fig = px.bar(supplier_risk, x="supplier_name", y="supplier_risk_score", color="risk_level", hover_data=["supplier_id","avg_lead_time","avg_on_time_rate","avg_defect_rate"], title="Supplier risk score")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff", xaxis_tickangle=-25)
            st.plotly_chart(fig, use_container_width=True)

    with tabs[5]:
        st.markdown("### What-if simulator results")
        st.markdown(f"<div class='panel'>Current scenario uses demand multiplier <b>{demand_multiplier:.2f}x</b>, supplier delay <b>{lead_time_delay} days</b>, service level <b>{int(service_level*100)}%</b>, and forecast horizon <b>{horizon_days} days</b>.</div>", unsafe_allow_html=True)
        scenario_cols = ["sku","product","stock","avg_daily_demand","lead_time_days","days_of_cover","reorder_point","recommended_order_qty","stockout_risk"]
        render_dark_table(model["inventory_health"][[c for c in scenario_cols if c in model["inventory_health"].columns]].replace([np.inf, -np.inf], np.nan).sort_values("recommended_order_qty", ascending=False), height=500)

    with tabs[6]:
        st.markdown("### Automation Center")
        st.markdown("These are approval-safe automation playbooks that can be wired into n8n, Zapier, Make, Airflow, cron, Slack, email, ERP, or a custom FastAPI backend.")
        render_dark_table(pd.DataFrame(model["automation_playbooks"]), height=280)
        st.markdown("### Alert queue")
        render_dark_table(pd.DataFrame(model["alerts"]), height=460)
        automation_json = make_automation_json(model, webhook_url)
        st.code(automation_json[:8000], language="json")

    with tabs[7]:
        st.markdown("### Procurement Assistant")
        suppliers = ["All suppliers"] + sorted(model["reorder_plan"]["supplier_id"].dropna().astype(str).unique().tolist()) if not model["reorder_plan"].empty and "supplier_id" in model["reorder_plan"].columns else ["All suppliers"]
        chosen_supplier = st.selectbox("Draft for supplier", suppliers)
        draft = procurement_email_draft(model["reorder_plan"], chosen_supplier)
        st.text_area("Approval-gated procurement draft", value=draft, height=360)
        st.caption("No email is sent automatically. This draft is for human review and approval.")

    with tabs[8]:
        st.markdown("### Executive report")
        st.markdown(report)

    with tabs[9]:
        st.markdown("### Export Center")
        audit_json = json.dumps(model_to_jsonable(model), indent=2, default=str)
        excel_bytes = make_excel_workbook(model, report)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.download_button("Download reorder CSV", data=df_to_csv_bytes(model["reorder_plan"]), file_name="supplychain_reorder_plan.csv", mime="text/csv", use_container_width=True)
        with c2:
            st.download_button("Download audit JSON", data=audit_json, file_name="supplychain_audit.json", mime="application/json", use_container_width=True)
        with c3:
            st.download_button("Download Excel pack", data=excel_bytes, file_name="supplychain_ops_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with c4:
            st.download_button("Download report MD", data=report, file_name="supplychain_executive_report.md", mime="text/markdown", use_container_width=True)
        st.download_button("Download automation JSON", data=make_automation_json(model, webhook_url), file_name="supplychain_automation_payload.json", mime="application/json", use_container_width=True)
else:
    st.divider()
    with st.expander("How to test quickly", expanded=True):
        st.markdown(
            """
            1. Keep **Use included sample supply-chain dataset** checked.
            2. Click **Load workspace**.
            3. Click **Run supply-chain analysis**.
            4. Open **Stockout Risk** to see critical SKUs.
            5. Open **Reorder Plan** to see recommended purchase quantities.
            6. Open **Supplier Risk** to review risky vendors.
            7. Open **What-If Simulator** and change demand/lead-time assumptions in the sidebar.
            8. Open **Automation Center** to see approval-safe playbooks and webhook JSON.
            9. Open **Export Center** to download CSV, JSON, Excel, and Markdown reports.
            """
        )

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
from datetime import datetime, timedelta
from src.supply_analysis import build_supply_model, make_report, model_to_jsonable, pick_tables, procurement_email_draft, z_for_service, score_suppliers_mcda, generate_rfq_draft
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
if "saved_scenarios" not in st.session_state:
    st.session_state.saved_scenarios = []

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

    tab_names = [
        "Inventory Health", "Demand Forecast", "SKU Detail Planner", "Stockout Risk", 
        "Reorder Plan", "Supplier scorecard & RFQ", "Returns & Quality", "Inter-DC Transfers",
        "What-If & Scenario Hub", "ROI & Cost Optimizer", "Automation Center", 
        "Procurement Assistant", "Executive Report", "Export Center"
    ]
    tabs = st.tabs(tab_names)
    (
        tab_inv, tab_forecast, tab_sku, tab_risk, 
        tab_reorder, tab_supplier, tab_returns, tab_transfers, 
        tab_whatif, tab_roi, tab_auto, tab_procure, tab_report, tab_export
    ) = tabs

    with tab_inv:
        st.markdown("### Inventory health overview")
        inv_health = model["inventory_health"].copy()
        fig_df = inv_health.replace([np.inf, -np.inf], np.nan).copy()
        if not fig_df.empty:
            fig = px.scatter(fig_df, x="days_of_cover", y="inventory_value", size="stock", color="stockout_risk", hover_data=["sku","product","abc_class"], title="Inventory value vs days of cover")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)
        render_dark_table(inv_health[[c for c in ["sku","product","stock","avg_daily_demand","days_of_cover","inventory_value","stockout_risk","dead_stock_flag","overstock_flag","abc_class"] if c in inv_health.columns]], height=420)

    with tab_forecast:
        st.markdown("### Demand forecast")
        df = model["inventory_health"].copy().replace([np.inf, -np.inf], np.nan).sort_values("forecast_horizon_qty", ascending=False)
        top = df.head(20)
        if not top.empty:
            fig = px.bar(top, x="sku", y="forecast_horizon_qty", color="stockout_risk", hover_data=["product","avg_daily_demand"], title=f"Forecast demand for next {horizon_days} days")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)
        render_dark_table(df[[c for c in ["sku","product","avg_daily_demand","std_daily_demand","forecast_horizon_qty","recent_30d_qty","annual_demand_qty","abc_class"] if c in df.columns]], height=420)

    with tab_sku:
        st.markdown("### SKU Detail Planner")
        # Select SKU
        unique_skus = sorted(model["inventory_health"]["sku"].unique())
        selected_sku = st.selectbox("Select SKU for detailed planning", unique_skus, key="detail_sku_select")
        
        # Get SKU details
        sku_row = model["inventory_health"][model["inventory_health"]["sku"] == selected_sku].iloc[0]
        st.markdown(f"**Product Name**: {sku_row['product']} | **Warehouse**: {sku_row.get('warehouse', 'Unassigned')} | **Supplier**: {sku_row.get('supplier_name', sku_row['supplier_id'])}")
        
        # Display small KPI metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Stock on Hand", f"{int(sku_row['stock'])}")
        with c2:
            st.metric("Days of Cover", f"{sku_row['days_of_cover']:.1f}" if sku_row['days_of_cover'] != np.inf else "∞")
        with c3:
            st.metric("Reorder Point", f"{int(round(sku_row['reorder_point']))}")
        with c4:
            st.metric("Safety Stock", f"{int(round(sku_row['safety_stock']))}")
        
        # Historical sales timeline and forecast projection
        sales_df = model["sales"]
        sku_sales = sales_df[sales_df["sku"] == selected_sku].copy()
        if not sku_sales.empty:
            # Aggregate sales daily
            sku_sales["date"] = pd.to_datetime(sku_sales["date"]).dt.normalize()
            daily_sales = sku_sales.groupby("date")["qty"].sum().reset_index().sort_values("date")
            
            # Create interactive line chart
            fig = go.Figure()
            # Historical sales line
            fig.add_trace(go.Scatter(x=daily_sales["date"], y=daily_sales["qty"], name="Historical Sales Qty", line=dict(color="#2f80ed", width=2)))
            
            # Forecast trend line starting at the end of history
            last_date = daily_sales["date"].max()
            forecast_dates = pd.date_range(last_date + pd.Timedelta(days=1), last_date + pd.Timedelta(days=horizon_days), freq="D")
            avg_demand = sku_row["avg_daily_demand"]
            forecast_qty = [avg_demand] * len(forecast_dates)
            fig.add_trace(go.Scatter(x=forecast_dates, y=forecast_qty, name="Forecasted Daily Demand", line=dict(color="#ff8a1f", dash="dash")))
            
            # Add horizontal line for Reorder Point and Safety Stock
            fig.add_hline(y=sku_row["reorder_point"], line_dash="dash", line_color="#ffb4ab", annotation_text="Reorder Point", annotation_position="top left")
            fig.add_hline(y=sku_row["safety_stock"], line_dash="dot", line_color="#ffe2a8", annotation_text="Safety Stock", annotation_position="bottom left")
            
            fig.update_layout(
                title=f"Historical Sales and {horizon_days}-Day Forecast Projection for {selected_sku}",
                xaxis_title="Date",
                yaxis_title="Quantity",
                height=450,
                paper_bgcolor="#070707",
                plot_bgcolor="#111111",
                font_color="#ffffff",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical sales data found for this SKU to plot.")

        # Explainable Operations mathematical solver details
        with st.expander("Explainable Operations (Mathematical Formula Breakdown)"):
            st.markdown("##### Recommendation Calculation Steps:")
            
            avg_demand = float(sku_row["avg_daily_demand"])
            lead_time = float(sku_row["lead_time_days"])
            safety_stock = float(sku_row["safety_stock"])
            reorder_point = float(sku_row["reorder_point"])
            stock = float(sku_row["stock"])
            incoming_qty = float(sku_row["incoming_qty"])
            net_position = stock + incoming_qty
            shortage_qty = float(sku_row["shortage_qty"])
            eoq = float(sku_row["eoq"])
            rec_qty = float(sku_row["recommended_order_qty"])
            unit_cost = float(sku_row["unit_cost"])
            
            st.markdown(f"""
            1. **Lead Time Demand**:
               $$\\text{{Lead Time Demand}} = \\text{{Avg Daily Demand}} \\times \\text{{Lead Time Days}}$$
               $$\\text{{Lead Time Demand}} = {avg_demand:.2f} \\times {lead_time:.1f} = {avg_demand * lead_time:.2f}\\text{{ units}}$$
               
            2. **Safety Stock**:
               $$\\text{{Safety Stock}} = z \\times \\sigma_d \\times \\sqrt{{L}}$$
               $$\\text{{Safety Stock}} = {model['params']['service_level']}\\text{{ z-score}} \\times {sku_row['std_daily_demand']:.2f} \\times \\sqrt{{{lead_time:.1f}}} = {safety_stock:.2f}\\text{{ units}}$$
               
            3. **Reorder Point (ROP)**:
               $$\\text{{ROP}} = \\text{{Lead Time Demand}} + \\text{{Safety Stock}}$$
               $$\\text{{ROP}} = {avg_demand * lead_time:.2f} + {safety_stock:.2f} = {reorder_point:.2f}\\text{{ units}}$$
               
            4. **Net Inventory Position**:
               $$\\text{{Net Position}} = \\text{{Stock On Hand}} + \\text{{Incoming Quantity}}$$
               $$\\text{{Net Position}} = {stock:.0f} + {incoming_qty:.0f} = {net_position:.0f}\\text{{ units}}$$
               
            5. **Net Shortage**:
               $$\\text{{Shortage}} = \\max(0, \\text{{ROP}} - \\text{{Net Position}})$$
               $$\\text{{Shortage}} = \\max(0, {reorder_point:.2f} - {net_position:.0f}) = {shortage_qty:.2f}\\text{{ units}}$$
               
            6. **Economic Order Quantity (EOQ)**:
               $$\\text{{EOQ}} = \\sqrt{{\\frac{{2 \\times \\text{{Annual Demand}} \\times \\text{{Order Cost}}}}{{\\text{{Holding Cost Rate}} \\times \\text{{Unit Cost}}}}}}$$
               $$\\text{{EOQ}} = \\sqrt{{\\frac{{2 \\times {sku_row['annual_demand_qty']:.1f} \\times {model['params']['order_cost']:.1f}}}{{{model['params']['holding_cost_rate']:.2f} \\times {unit_cost:.2f}}}}} = {eoq:.2f}\\text{{ units}}$$
               
            7. **Final Recommended Order Quantity**:
               $$\\text{{Final Order Qty}} = \\max(\\text{{Shortage}}, \\text{{EOQ}} \\times (\\text{{Shortage}} > 0))$$
               $$\\text{{Final Order Qty}} = \\max({shortage_qty:.2f}, {eoq:.2f} \\times ({shortage_qty:.2f} > 0)) = {rec_qty:.0f}\\text{{ units}}$$
            """)

    with tab_risk:
        st.markdown("### Stockout and overstock risk")
        risk_df = model["inventory_health"].copy().replace([np.inf, -np.inf], np.nan)
        risk_counts = risk_df["stockout_risk"].value_counts().reset_index()
        risk_counts.columns = ["risk", "count"]
        fig = px.pie(risk_counts, names="risk", values="count", title="Risk distribution")
        fig.update_layout(height=380, paper_bgcolor="#070707", font_color="#ffffff")
        st.plotly_chart(fig, use_container_width=True)
        render_dark_table(risk_df.sort_values(["stockout_risk","days_of_cover"])[[c for c in ["sku","product","stock","incoming_qty","days_of_cover","lead_time_days","reorder_point","shortage_qty","stockout_risk","supplier_name"] if c in risk_df.columns]], height=460)

    with tab_reorder:
        st.markdown("### Reorder plan")
        reorder = model["reorder_plan"]
        if reorder.empty:
            st.success("No reorder recommendations under the current scenario.")
        else:
            render_dark_table(reorder, height=500)
            fig = px.bar(reorder.head(20), x="sku", y="recommended_order_value", color="stockout_risk", hover_data=["product","recommended_order_qty"], title="Top reorder value recommendations")
            fig.update_layout(height=420, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig, use_container_width=True)

    with tab_supplier:
        st.markdown("### Supplier Scorecard & RFQ Writer")
        st.markdown("<span class='small-muted'>Use Multi-Criteria Decision Analysis (MCDA) to rank suppliers dynamically. Then, instantly draft quote requests.</span>", unsafe_allow_html=True)
        
        # MCDA weights controllers
        st.markdown("##### 1. Configure Evaluation Weights")
        wc1, wc2, wc3, wc4 = st.columns(4)
        with wc1:
            w_price = st.slider("Price Weight (Cost)", 0.0, 1.0, 0.3, step=0.05, key="w_price_slider")
        with wc2:
            w_speed = st.slider("Speed Weight (Lead Time)", 0.0, 1.0, 0.2, step=0.05, key="w_speed_slider")
        with wc3:
            w_reliability = st.slider("Reliability Weight (On-Time)", 0.0, 1.0, 0.3, step=0.05, key="w_reliability_slider")
        with wc4:
            w_quality = st.slider("Quality Weight (Quality Rate)", 0.0, 1.0, 0.2, step=0.05, key="w_quality_slider")
            
        # Run MCDA scoring
        supplier_risk = model["supplier_risk"]
        mcda_df = score_suppliers_mcda(supplier_risk, w_price, w_speed, w_reliability, w_quality)
        
        if mcda_df.empty:
            st.info("No supplier data loaded.")
        else:
            # Sorted by score
            mcda_df = mcda_df.sort_values("mcda_score", ascending=False)
            
            # Plot scores
            fig_score = px.bar(
                mcda_df, 
                x="supplier_name", 
                y="mcda_score", 
                color="mcda_score", 
                color_continuous_scale="Oranges", 
                hover_data=["risk_level", "avg_lead_time", "avg_on_time_rate", "avg_defect_rate"],
                title="Supplier Scorecard Rankings (Weighted MCDA)"
            )
            fig_score.update_layout(height=400, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig_score, use_container_width=True)
            
            # Render details
            render_dark_table(mcda_df[["supplier_id", "supplier_name", "mcda_score", "avg_unit_cost", "avg_lead_time", "avg_on_time_rate", "avg_defect_rate", "risk_level"]], height=320)
            
        # RFQ Writer Section
        st.divider()
        st.markdown("##### 2. Supplier Request for Quote (RFQ) Writer")
        rfq_suppliers = sorted(model["supplier_risk"]["supplier_name"].unique()) if not model["supplier_risk"].empty else []
        rfq_skus = sorted(model["inventory_health"]["sku"].unique()) if not model["inventory_health"].empty else []
        
        if rfq_suppliers and rfq_skus:
            rfqc1, rfqc2 = st.columns(2)
            with rfqc1:
                sel_supp = st.selectbox("Select Supplier", rfq_suppliers, key="rfq_supp_select")
                sel_sku = st.selectbox("Select Product SKU", rfq_skus, key="rfq_sku_select")
                
                # Fetch SKU specific product name and unit cost to populate defaults
                sku_data = model["inventory_health"][model["inventory_health"]["sku"] == sel_sku].iloc[0]
                default_prod = sku_data["product"]
                default_cost = float(sku_data["unit_cost"])
                
                # Recommended quantity from model
                rec_qty_val = float(sku_data["recommended_order_qty"])
                default_qty = int(rec_qty_val) if rec_qty_val > 0 else 100
                
            with rfqc2:
                rfq_qty = st.number_input("Order Quantity", min_value=1, value=default_qty, step=50, key="rfq_qty_input")
                rfq_price = st.number_input("Target Unit Price ($)", min_value=0.0, value=default_cost, step=1.0, key="rfq_price_input")
                rfq_delivery = st.text_input("Requested Delivery Date", value=(datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d"), key="rfq_delivery_input")
            
            # Generate email
            rfq_email = generate_rfq_draft(sel_supp, sel_sku, default_prod, rfq_qty, rfq_price, rfq_delivery)
            st.text_area("Generated RFQ Email Draft", value=rfq_email, height=300)
            st.caption("Review and edit this draft before sending to your vendor.")
        else:
            st.info("Suppliers or inventory data not available to generate RFQ.")

    with tab_returns:
        st.markdown("### Returns & Quality Analytics")
        if model["returns"].empty:
            st.info("No returns data uploaded or loaded in the workspace.")
        else:
            k_ret = model["kpis"]
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                metric_card("Total Returns Quantity", f"{k_ret.get('total_returns_qty', 0):,}", "Units returned by customers")
            with col_r2:
                metric_card("Total Refund Value", f"${money(k_ret.get('total_refund_value', 0))}", "Direct capital loss")
            with col_r3:
                # Calculate return rate overall
                total_sales_all = model["sales"]["qty"].sum() if not model["sales"].empty else 1
                overall_ret_rate = k_ret.get('total_returns_qty', 0) / total_sales_all if total_sales_all > 0 else 0.0
                metric_card("Overall Return Rate", f"{overall_ret_rate * 100:.2f}%", "Returns vs. total sales volume")

            # Returns by Reason chart & table
            st.markdown("#### Return Reasons Breakdown")
            reasons_list = model["returns_by_reason"]
            if reasons_list:
                reasons_df = pd.DataFrame(reasons_list)
                fig_reasons = px.pie(reasons_df, names="reason", values="return_qty", title="Return Quantity by Reason")
                fig_reasons.update_layout(height=380, paper_bgcolor="#070707", font_color="#ffffff")
                st.plotly_chart(fig_reasons, use_container_width=True)
                render_dark_table(reasons_df, height=200)

            # SKU Return Rates
            st.markdown("#### SKU Return Rates & Rankings")
            sku_ret_df = model["sku_returns"].copy().sort_values("return_rate", ascending=False)
            sku_ret_df["return_rate"] = sku_ret_df["return_rate"].map(lambda x: f"{x*100:.2f}%")
            render_dark_table(sku_ret_df[["sku", "product", "total_return_qty", "total_sales_qty", "return_rate", "total_refund_amount"]], height=320)

            # Supplier Quality Correlation
            st.markdown("#### Supplier Quality and Defect Correlation")
            st.markdown("<span class='small-muted'>This correlates quality/damage returns from customers with your supplier's self-reported defect rates.</span>", unsafe_allow_html=True)
            supp_ret_df = model["supplier_returns"].copy()
            if not supp_ret_df.empty:
                # Merge with supplier risk to get self-reported defect rate
                supp_ret_df = supp_ret_df.merge(model["supplier_risk"][["supplier_id", "avg_defect_rate"]], on="supplier_id", how="left")
                fig_supp = px.scatter(
                    supp_ret_df, 
                    x="avg_defect_rate", 
                    y="supplier_quality_return_qty", 
                    size="supplier_refund_amount",
                    hover_name="supplier_name", 
                    title="Supplier Defect Rate vs Customer Quality Returns",
                    labels={"avg_defect_rate": "Supplier Defect Rate", "supplier_quality_return_qty": "Quality/Damaged Returns (Qty)"}
                )
                fig_supp.update_layout(height=400, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
                st.plotly_chart(fig_supp, use_container_width=True)
                render_dark_table(supp_ret_df[["supplier_id", "supplier_name", "supplier_return_qty", "supplier_refund_amount", "supplier_quality_return_qty", "avg_defect_rate"]], height=260)

    with tab_transfers:
        st.markdown("### Inter-DC Inventory Transfer Advisor")
        st.markdown("<span class='small-muted'>Re-routing excess stock between warehouses can satisfy local stockouts without initiating new purchase orders.</span>", unsafe_allow_html=True)
        
        k_trans = model["kpis"]
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            metric_card("Potential Saved Value", f"${money(k_trans.get('saved_transfer_value', 0))}", "Cost of purchases avoided")
        with col_t2:
            metric_card("Transfer Opportunities", f"{k_trans.get('transfers_count', 0)}", "SKU routing adjustments available")
            
        trans_df = model["transfers"]
        if trans_df.empty:
            st.success("No warehouse transfer opportunities detected under the current stock configuration.")
        else:
            render_dark_table(trans_df, height=450)
            fig_trans = px.bar(
                trans_df.sort_values("saved_value", ascending=False).head(15), 
                x="sku", 
                y="saved_value", 
                color="qty", 
                hover_data=["from_warehouse", "to_warehouse"], 
                title="Top Transfers by Financial Value"
            )
            fig_trans.update_layout(height=400, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
            st.plotly_chart(fig_trans, use_container_width=True)

    with tab_whatif:
        st.markdown("### What-if Simulator & Scenario Hub")
        st.markdown(f"<div class='panel'>Current scenario uses demand multiplier <b>{demand_multiplier:.2f}x</b>, supplier delay <b>{lead_time_delay} days</b>, service level <b>{int(service_level*100)}%</b>, and forecast horizon <b>{horizon_days} days</b>.</div>", unsafe_allow_html=True)
        
        # Save Current Scenario Form
        st.markdown("##### Save Current Scenario Config")
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            sc_name = st.text_input("Scenario Label / Name", value=f"Scenario {len(st.session_state.saved_scenarios) + 1}", key="sc_name_input")
        with col_s2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            save_clicked = st.button("Save Scenario", use_container_width=True)
            
        if save_clicked:
            # Check if name already exists, remove it
            st.session_state.saved_scenarios = [s for s in st.session_state.saved_scenarios if s["name"] != sc_name]
            st.session_state.saved_scenarios.append({
                "name": sc_name,
                "demand_multiplier": demand_multiplier,
                "lead_time_delay": lead_time_delay,
                "service_level": service_level,
                "total_inventory_value": float(model["kpis"]["total_inventory_value"]),
                "recommended_order_value": float(model["kpis"]["recommended_order_value"]),
                "critical_skus": int(model["kpis"]["critical_skus"])
            })
            st.success(f"Successfully saved scenario '{sc_name}'!")
            
        # Display saved scenarios comparison if they exist
        if st.session_state.saved_scenarios:
            st.divider()
            st.markdown("##### Saved Scenarios Comparison")
            sc_df = pd.DataFrame(st.session_state.saved_scenarios)
            
            # Display comparison table
            render_dark_table(sc_df, height=200)
            
            # Draw charts
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                fig_sc_val = px.bar(
                    sc_df, x="name", y=["total_inventory_value", "recommended_order_value"],
                    barmode="group", title="Carrying Value vs Reorder Value ($)",
                    labels={"value": "Amount ($)", "variable": "Metric"}
                )
                fig_sc_val.update_layout(height=350, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
                st.plotly_chart(fig_sc_val, use_container_width=True)
            with c_s2:
                fig_sc_crit = px.bar(
                    sc_df, x="name", y="critical_skus",
                    title="Critical Stockout SKUs Count",
                    labels={"critical_skus": "SKUs Count"}
                )
                fig_sc_crit.update_layout(height=350, paper_bgcolor="#070707", plot_bgcolor="#111111", font_color="#ffffff")
                st.plotly_chart(fig_sc_crit, use_container_width=True)
                
            if st.button("Clear Saved Scenarios", key="clear_scenarios_btn"):
                st.session_state.saved_scenarios = []
                st.rerun()

        st.divider()
        st.markdown("##### Scenario Details Table")
        scenario_cols = ["sku","product","stock","avg_daily_demand","lead_time_days","days_of_cover","reorder_point","recommended_order_qty","stockout_risk"]
        render_dark_table(model["inventory_health"][[c for c in scenario_cols if c in model["inventory_health"].columns]].replace([np.inf, -np.inf], np.nan).sort_values("recommended_order_qty", ascending=False), height=500)

    with tab_roi:
        st.markdown("### ROI & Service-Level Cost Optimizer")
        st.markdown("<span class='small-muted'>Optimize service level by finding the minimum total cost point where safety stock holding costs and stockout penalties intersect.</span>", unsafe_allow_html=True)
        
        # User input for custom stockout penalty multiplier
        penalty_mult = st.slider("Stockout penalty multiplier (x Unit Cost)", 1.0, 5.0, 1.5, step=0.1, key="penalty_mult_slider")
        
        # Recalculate cost curves dynamically based on custom penalty multiplier
        service_levels = [0.80, 0.85, 0.90, 0.95, 0.98, 0.99]
        dynamic_curves = []
        for sl in service_levels:
            z_score = z_for_service(sl)
            total_carrying = 0.0
            total_stockout = 0.0
            for _, row in model["inventory_health"].iterrows():
                std_demand = row.get("std_daily_demand", 0)
                lead_time = row.get("lead_time_days", 10)
                unit_cost = row.get("unit_cost", 0)
                annual_demand = row.get("annual_demand_qty", 0)
                
                ss = z_score * std_demand * np.sqrt(max(1, lead_time))
                carrying = ss * unit_cost * model["params"]["holding_cost_rate"]
                
                penalty = max(1.0, unit_cost * penalty_mult)
                shortage = (1 - sl) * annual_demand
                stockout = shortage * penalty
                
                total_carrying += carrying
                total_stockout += stockout
                
            dynamic_curves.append({
                "Service Level": f"{int(sl*100)}%",
                "Carrying Cost": total_carrying,
                "Stockout Cost": total_stockout,
                "Total Cost": total_carrying + total_stockout
            })
            
        curves_df = pd.DataFrame(dynamic_curves)
        
        # Plot Plotly chart
        fig_roi = go.Figure()
        fig_roi.add_trace(go.Scatter(x=curves_df["Service Level"], y=curves_df["Carrying Cost"], name="Carrying Cost of Safety Stock", line=dict(color="#ffe2a8", width=2)))
        fig_roi.add_trace(go.Scatter(x=curves_df["Service Level"], y=curves_df["Stockout Cost"], name="Expected Stockout Cost", line=dict(color="#ffb4ab", width=2)))
        fig_roi.add_trace(go.Scatter(x=curves_df["Service Level"], y=curves_df["Total Cost"], name="Total Optimization Cost", line=dict(color="#2f80ed", width=3, dash="solid")))
        
        # Find optimal service level
        min_row = curves_df.loc[curves_df["Total Cost"].idxmin()]
        opt_sl = min_row["Service Level"]
        
        fig_roi.update_layout(
            title=f"Cost Tradeoff Curve (Optimal Service Level: {opt_sl})",
            xaxis_title="Service Level",
            yaxis_title="Estimated Annual Cost ($)",
            height=450,
            paper_bgcolor="#070707",
            plot_bgcolor="#111111",
            font_color="#ffffff",
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99)
        )
        st.plotly_chart(fig_roi, use_container_width=True)
        
        st.markdown(f"##### Recommended Target: **{opt_sl} Service Level**")
        st.markdown(f"At this target level, the estimated carrying cost is **${min_row['Carrying Cost']:,.2f}** and expected stockout penalty is **${min_row['Stockout Cost']:,.2f}**, leading to the minimum total cost of **${min_row['Total Cost']:,.2f}** per year.")

    with tab_auto:
        st.markdown("### Automation Center")
        st.markdown("These are approval-safe automation playbooks that can be wired into n8n, Zapier, Make, Airflow, cron, Slack, email, ERP, or a custom FastAPI backend.")
        render_dark_table(pd.DataFrame(model["automation_playbooks"]), height=280)
        st.markdown("### Alert queue")
        render_dark_table(pd.DataFrame(model["alerts"]), height=460)
        automation_json = make_automation_json(model, webhook_url)
        st.code(automation_json[:8000], language="json")

    with tab_procure:
        st.markdown("### Procurement Assistant")
        suppliers = ["All suppliers"] + sorted(model["reorder_plan"]["supplier_id"].dropna().astype(str).unique().tolist()) if not model["reorder_plan"].empty and "supplier_id" in model["reorder_plan"].columns else ["All suppliers"]
        chosen_supplier = st.selectbox("Draft for supplier", suppliers)
        draft = procurement_email_draft(model["reorder_plan"], chosen_supplier)
        st.text_area("Approval-gated procurement draft", value=draft, height=360)
        st.caption("No email is sent automatically. This draft is for human review and approval.")

    with tab_report:
        st.markdown("### Executive report")
        st.markdown(report)

    with tab_export:
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

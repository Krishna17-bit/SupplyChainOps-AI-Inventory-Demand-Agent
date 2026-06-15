# SupplyChainOps AI — Inventory, Demand Forecasting & Procurement Agent

SupplyChainOps AI is a local Streamlit command center for supply-chain operations. It analyzes sales history, inventory snapshots, suppliers, purchase orders, returns, and optional database tables to produce demand forecasts, reorder plans, stockout risk, supplier risk, what-if scenarios, procurement drafts, automation playbooks, and audit-ready exports.

## Features

- **Multi-Source Data Ingestion**: Seamless ingestion of CSV, Excel, JSON, SQLite files, and live database tables via SQLAlchemy connections.
- **Auto-Role & Normalization Pipeline**: Intelligently detects and maps uploaded data into standardized roles (Sales, Inventory, Suppliers, Purchase Orders, Returns, and BOM Recipes).
- **Explainable Operations Solver**: Expands step-by-step LaTeX math formulas (Lead-Time Demand, Safety Stock, ROP, EOQ, Shortages) in the UI for auditable decision-making.
- **Bill of Materials (BOM) Component Planner**: Explodes parent finished good demand forecasts into component-level raw material shortages and tracks raw component replenishment.
- **Air vs. Ocean Freight Cost-Tradeoff Optimizer**: Compares transportation rates, lead-time safety stock holding cost, and pipeline transit cost to recommend optimal shipping splits.
- **Financial Health & Velocity Dashboard**: Tracks metrics like portfolio Days Inventory Outstanding (DIO), Inventory Turnover Ratio (ITR), and carrying costs segmented by storage class (Standard, Fragile, Cold-Chain).
- **Multi-Criteria Decision Analysis (MCDA) Supplier Scorecard**: Dynamic supplier evaluation based on weighted attributes (Price, Speed, Reliability, Quality) with interactive ranking charts.
- **Interactive What-If Scenario Hub**: Simulate, save, and compare multiple operational configurations (demand multipliers, lead-time delays) side-by-side.
- **Supplier RFQ & Procurement Assistant**: Automatically draft vendor RFQ emails pre-populated with target cost-points and recommended order quantities.
- **Inter-DC Transfer Advisor**: Identifies surplus and deficit stock levels across different warehouses and suggests transfers to save procurement capital.
- **Returns & Quality Analytics**: Correlates customer returns by reason with supplier defect rates to pinpoint quality issues.
- **SaaS-Grade Monochrome Theme**: Designed with a sleek, high-contrast pure black and charcoal interface (`#000000`/`#0a0a0a`) featuring vibrant orange and cobalt blue interactive controls.
- **Webhook-Ready Automation**: Exports approval-gated cron/Zapier/n8n automation playbooks and JSON payloads.
- **Comprehensive Audit Package**: Single-click downloads for executive reports (Markdown), reorder logs (CSV), raw audits (JSON), and multi-sheet Excel workbooks (`bom_recipes`, `freight_optimization`, `financial_kpis`).

## Run locally

```powershell
python -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Optional AI reasoning

Open `.env` and add:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=
```

The UI does not show provider/model names. Local analytics, forecasting, optimization, risk scoring, procurement drafts, and exports work even without an API key.

## Optional database connector

You can connect a local/private database using either:

1. Upload a SQLite `.db`, `.sqlite`, or `.sqlite3` file.
2. Enter a local SQLite path in the UI.
3. Add a SQLAlchemy URL in `.env`:

```env
SUPPLYCHAIN_DB_URL=sqlite:///C:/path/to/inventory.db
```

For Postgres/MySQL, install the relevant driver locally and use a SQLAlchemy URL. The app imports only selected tables with read-only `SELECT ... LIMIT` style pulls.

## Quick test

1. Run the app.
2. Keep **Use included sample supply-chain dataset** checked.
3. Click **Load workspace**.
4. Click **Run supply-chain analysis**.
5. Review Inventory Health, Demand Forecast, SKU Detail Planner, BOM Planner, Stockout Risk, Reorder Plan, Supplier scorecard & RFQ, Freight Optimizer, Returns & Quality, Inter-DC Transfers, Financial Health & Velocity, What-If & Scenario Hub, ROI & Cost Optimizer, Automation Center, and Export Center.

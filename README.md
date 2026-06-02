# SupplyChainOps AI — Inventory, Demand Forecasting & Procurement Agent

SupplyChainOps AI is a local Streamlit command center for supply-chain operations. It analyzes sales history, inventory snapshots, suppliers, purchase orders, returns, and optional database tables to produce demand forecasts, reorder plans, stockout risk, supplier risk, what-if scenarios, procurement drafts, automation playbooks, and audit-ready exports.

## Features

- CSV, Excel, JSON, SQLite, and database-table ingestion
- Optional personal database connector through SQLAlchemy URL
- Multi-table workspace with role detection
- Sales, inventory, supplier, purchase-order, and returns normalization
- Demand forecasting by SKU/product
- Safety stock calculation
- Reorder point calculation
- EOQ-style reorder recommendation
- Stockout risk scoring
- Overstock and dead-stock detection
- ABC inventory classification
- Supplier risk scoring
- Purchase-order and incoming-stock awareness
- Demand spike anomaly detection
- What-if simulation for demand increases and supplier delays
- Procurement email draft generator with human approval gate
- Automation playbooks for n8n/Zapier/Make/Airflow/cron/custom APIs
- Webhook-ready automation JSON export
- Executive report generation
- Reorder CSV export
- Audit JSON export
- Excel export pack
- Optional AI narrative reasoning through `.env`

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
5. Review Inventory Health, Demand Forecast, Stockout Risk, Reorder Plan, Supplier Risk, Automation Center, and Export Center.

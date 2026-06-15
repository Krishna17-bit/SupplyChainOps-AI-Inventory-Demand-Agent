APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --bg: #000000;
    --panel: #0a0a0a;
    --panel-2: #121212;
    --text: #f3f4f6;
    --muted: #9ca3af;
    --border: #1f2937;
    --orange: #ff6b00;
    --orange-hover: #ff8522;
    --blue: #0055ff;
    --blue-hover: #3377ff;
    --danger: #fca5a5;
    --warn: #fde047;
    --ok: #86efac;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] {
    background: rgba(0,0,0,0.9) !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1500px !important;
}

[data-testid="stSidebar"] {
    background: #050505 !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}

h1, h2, h3, h4, h5, h6, p, li, label, span, strong {
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}

.small-muted {
    color: var(--muted) !important;
    font-size: .88rem;
    line-height: 1.5;
}

.hero {
    border: 1px solid var(--border);
    background: radial-gradient(circle at top right, rgba(0, 85, 255, 0.08), transparent 35%), linear-gradient(135deg, #0a0a0a 0%, #030303 100%);
    border-radius: 20px;
    padding: 28px;
    margin-bottom: 24px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.7);
}

.hero-title {
    color: #ffffff !important;
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    margin-bottom: 8px;
}

.hero-subtitle {
    color: #d1d5db !important;
    font-size: 1.0rem;
    line-height: 1.6;
    max-width: 1000px;
}

.panel {
    border: 1px solid var(--border);
    background: var(--panel);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}

.metric-card {
    border: 1px solid var(--border);
    background: var(--panel-2);
    border-radius: 14px;
    padding: 18px;
    min-height: 110px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.metric-label {
    color: var(--muted) !important;
    font-size: .82rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}

.metric-value {
    color: #ffffff !important;
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.metric-note {
    color: var(--muted) !important;
    font-size: .8rem;
    margin-top: 6px;
}

.status-pill {
    display: inline-block;
    border: 1px solid var(--border);
    background: #000000;
    color: var(--text) !important;
    border-radius: 999px;
    padding: 4px 12px;
    font-size: .8rem;
    font-weight: 550;
    margin: 2px 4px 2px 0;
}

.pill-danger { border-color: #ef4444; color: var(--danger) !important; }
.pill-warn { border-color: #eab308; color: var(--warn) !important; }
.pill-ok { border-color: #22c55e; color: var(--ok) !important; }

.stButton > button {
    background: var(--orange) !important;
    color: #000000 !important;
    border: 1px solid var(--orange) !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    min-height: 42px !important;
    box-shadow: 0 4px 15px rgba(255,107,0,0.15) !important;
    transition: all 0.2s ease-in-out !important;
}

.stButton > button:hover {
    background: var(--orange-hover) !important;
    border-color: var(--orange-hover) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(255,107,0,0.25) !important;
}

.stButton > button p, .stButton > button span, .stButton > button div {
    color: #000000 !important;
    font-weight: 700 !important;
}

.stDownloadButton > button {
    background: var(--blue) !important;
    color: #ffffff !important;
    border: 1px solid var(--blue) !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    min-height: 42px !important;
    box-shadow: 0 4px 15px rgba(0,85,255,0.15) !important;
    transition: all 0.2s ease-in-out !important;
}

.stDownloadButton > button:hover {
    background: var(--blue-hover) !important;
    border-color: var(--blue-hover) !important;
    color: #ffffff !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0,85,255,0.25) !important;
}

.stDownloadButton > button p, .stDownloadButton > button span, .stDownloadButton > button div {
    color: #ffffff !important;
    font-weight: 700 !important;
}

[data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"] {
    background: #080808 !important;
    border: 1px dashed var(--border) !important;
    border-radius: 12px !important;
}

[data-testid="stFileUploader"] section *, [data-testid="stFileUploaderDropzone"] * {
    color: #e5e7eb !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background: var(--blue) !important;
    color: #ffffff !important;
    border: 1px solid var(--blue) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: #050505 !important;
    color: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

.stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
    background: #050505 !important;
    color: #ffffff !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
}

.stSelectbox *, .stMultiSelect *, .stCheckbox *, .stSlider *, .stRadio * {
    color: #ffffff !important;
}

[data-baseweb="popover"], [data-baseweb="menu"] {
    background: #0a0a0a !important;
    color: #ffffff !important;
    border: 1px solid var(--border) !important;
}

[data-baseweb="menu"] ul, [data-baseweb="menu"] li, [role="listbox"], [role="option"] {
    background: #0a0a0a !important;
    color: #ffffff !important;
}

[role="option"]:hover {
    background: #18181b !important;
    color: #ffffff !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid var(--border);
}

.stTabs [data-baseweb="tab"] {
    background: #070707 !important;
    border-radius: 6px 6px 0 0 !important;
    border: 1px solid var(--border) !important;
    border-bottom: none !important;
    color: var(--muted) !important;
    padding: 8px 14px !important;
    font-weight: 600 !important;
}

.stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] span, .stTabs [data-baseweb="tab"] div {
    color: var(--muted) !important;
    font-weight: 600 !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: var(--panel) !important;
    border-color: var(--border) !important;
    border-bottom: 1px solid var(--panel) !important;
    color: var(--orange) !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] p, .stTabs [data-baseweb="tab"][aria-selected="true"] span, .stTabs [data-baseweb="tab"][aria-selected="true"] div {
    color: var(--orange) !important;
    font-weight: 700 !important;
}

.dark-table-scroll {
    width: 100%;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #050505;
    margin-top: 10px;
    margin-bottom: 16px;
}

.dark-table-scroll table {
    width: 100%;
    border-collapse: collapse;
    background: #050505 !important;
    color: #ffffff !important;
    font-size: .9rem;
}

.dark-table-scroll thead tr {
    background: #0c0c0c !important;
}

.dark-table-scroll th {
    color: #ffffff !important;
    background: #0c0c0c !important;
    border-bottom: 1px solid var(--border) !important;
    padding: 10px 12px;
    text-align: left;
    font-weight: 700;
    position: sticky;
    top: 0;
    z-index: 1;
    white-space: nowrap;
}

.dark-table-scroll td {
    color: #d1d5db !important;
    background: #050505 !important;
    border-bottom: 1px solid #111827 !important;
    padding: 10px 12px;
    vertical-align: top;
}

.dark-table-scroll tr:hover td {
    background: #0a0a0a !important;
}

[data-testid="stAlert"] {
    background: #0a0a0a !important;
    color: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}

[data-testid="stAlert"] * {
    color: #ffffff !important;
}

.streamlit-expanderHeader, [data-testid="stExpander"] details summary {
    background: #0a0a0a !important;
    color: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

code, pre {
    color: #f3f4f6 !important;
    background: #080808 !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

hr {
    border-color: var(--border) !important;
}

a {
    color: var(--blue-hover) !important;
}

[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
    color: #9ca3af !important;
}

#MainMenu, footer {
    visibility: hidden;
}
</style>
"""

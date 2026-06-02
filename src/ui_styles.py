APP_CSS = """
<style>
:root {
    --bg: #070707;
    --panel: #111111;
    --panel-2: #171717;
    --text: #f7f7f7;
    --muted: #b9b9b9;
    --border: #2a2a2a;
    --orange: #ff8a1f;
    --orange-hover: #ffa64d;
    --blue: #2f80ed;
    --blue-hover: #54a1ff;
    --danger: #ffb4ab;
    --warn: #ffe2a8;
    --ok: #c9f7d2;
}
html, body, .stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: rgba(7,7,7,0.92) !important; }
.block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; max-width: 1500px !important; }
[data-testid="stSidebar"] { background: #0c0c0c !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] * { color: var(--text) !important; }
h1,h2,h3,h4,h5,h6,p,li,label { color: var(--text) !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] strong { color: var(--text) !important; }
.small-muted { color: var(--muted) !important; font-size: .9rem; line-height: 1.55; }
.hero { border:1px solid var(--border); background: radial-gradient(circle at top right, rgba(47,128,237,.20), transparent 28%), radial-gradient(circle at bottom left, rgba(255,138,31,.11), transparent 30%), linear-gradient(135deg,#151515 0%,#090909 62%,#161616 100%); border-radius:26px; padding:30px; margin-bottom:22px; box-shadow:0 20px 55px rgba(0,0,0,.38); }
.hero-title { color:#fff !important; font-size:2.45rem; font-weight:900; letter-spacing:-.045em; margin-bottom:10px; }
.hero-subtitle { color:#cfcfcf !important; font-size:1.04rem; line-height:1.65; max-width:1050px; }
.panel { border:1px solid var(--border); background:var(--panel); border-radius:18px; padding:18px; margin-bottom:14px; box-shadow:0 10px 30px rgba(0,0,0,.22); }
.panel * { color: var(--text) !important; }
.metric-card { border:1px solid var(--border); background:var(--panel-2); border-radius:18px; padding:16px; min-height:112px; }
.metric-card * { color:var(--text) !important; }
.metric-label { color:var(--muted) !important; font-size:.86rem; margin-bottom:8px; }
.metric-value { color:#fff !important; font-size:1.75rem; font-weight:900; letter-spacing:-.035em; }
.metric-note { color:var(--muted) !important; font-size:.82rem; margin-top:8px; }
.status-pill { display:inline-block; border:1px solid var(--border); background:#0d0d0d; color:var(--text) !important; border-radius:999px; padding:4px 10px; font-size:.82rem; margin:2px 4px 2px 0; }
.pill-danger { border-color:#6a2a2a; color:var(--danger) !important; }
.pill-warn { border-color:#725518; color:var(--warn) !important; }
.pill-ok { border-color:#1d5e30; color:var(--ok) !important; }
.evidence { border-left:3px solid var(--blue); background:#101010; border-radius:12px; padding:12px 14px; margin:9px 0; color:var(--text) !important; }
.evidence b { color:#fff !important; }
.stButton > button { background: var(--orange) !important; color:#0b0b0b !important; border:1px solid var(--orange) !important; border-radius:13px !important; font-weight:850 !important; min-height:44px !important; box-shadow:0 8px 22px rgba(255,138,31,.18) !important; }
.stButton > button:hover { background:var(--orange-hover) !important; color:#000 !important; border-color:var(--orange-hover) !important; }
.stButton > button:disabled, .stButton > button[disabled] { background:#242424 !important; color:#777 !important; border-color:#333 !important; box-shadow:none !important; }
.stButton > button p, .stButton > button span, .stButton > button div { color:#0b0b0b !important; font-weight:850 !important; }
.stButton > button:disabled p, .stButton > button:disabled span, .stButton > button:disabled div { color:#777 !important; }
.stDownloadButton > button { background:var(--blue) !important; color:#fff !important; border:1px solid var(--blue) !important; border-radius:13px !important; font-weight:850 !important; min-height:44px !important; box-shadow:0 8px 22px rgba(47,128,237,.18) !important; }
.stDownloadButton > button:hover { background:var(--blue-hover) !important; border-color:var(--blue-hover) !important; color:#fff !important; }
.stDownloadButton > button p, .stDownloadButton > button span, .stDownloadButton > button div { color:#fff !important; font-weight:850 !important; }
[data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"] { background:#111111 !important; border:1px dashed #3a3a3a !important; border-radius:16px !important; }
[data-testid="stFileUploader"] section *, [data-testid="stFileUploaderDropzone"] * { color:#e9e9e9 !important; }
[data-testid="stFileUploaderDropzone"] button { background:var(--blue) !important; color:#fff !important; border:1px solid var(--blue) !important; border-radius:12px !important; font-weight:850 !important; }
[data-testid="stFileUploaderDropzone"] button:hover { background:var(--blue-hover) !important; border-color:var(--blue-hover) !important; color:#fff !important; }
[data-testid="stFileUploaderDropzone"] button p, [data-testid="stFileUploaderDropzone"] button span, [data-testid="stFileUploaderDropzone"] button div { color:#fff !important; font-weight:850 !important; }
.stTextInput input, .stTextArea textarea, .stNumberInput input { background:#101010 !important; color:#fff !important; border:1px solid var(--border) !important; border-radius:12px !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:#888 !important; }
.stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div { background:#101010 !important; color:#fff !important; border-color:var(--border) !important; border-radius:12px !important; }
.stSelectbox *, .stMultiSelect *, .stCheckbox *, .stSlider *, .stRadio * { color:#fff !important; }
[data-baseweb="popover"], [data-baseweb="menu"] { background:#111111 !important; color:#ffffff !important; border:1px solid var(--border) !important; }
[data-baseweb="menu"] ul, [data-baseweb="menu"] li, [role="listbox"], [role="option"] { background:#111111 !important; color:#ffffff !important; }
[role="option"]:hover { background:#1b1b1b !important; color:#ffffff !important; }
[aria-selected="true"] { background:rgba(47,128,237,.28) !important; color:#ffffff !important; }
.stTabs [data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid var(--border); }
.stTabs [data-baseweb="tab"] { background:#111 !important; border-radius:999px !important; border:1px solid var(--border) !important; color:#fff !important; padding:9px 16px !important; font-weight:750 !important; }
.stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] span, .stTabs [data-baseweb="tab"] div { color:#fff !important; font-weight:750 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { background:var(--orange) !important; border-color:var(--orange) !important; color:#111 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] p, .stTabs [data-baseweb="tab"][aria-selected="true"] span, .stTabs [data-baseweb="tab"][aria-selected="true"] div { color:#111 !important; font-weight:850 !important; }
.dark-table-scroll { width:100%; overflow:auto; border:1px solid var(--border); border-radius:16px; background:#101010; margin-top:12px; margin-bottom:18px; }
.dark-table-scroll table { width:100%; border-collapse:collapse; background:#101010 !important; color:#ffffff !important; font-size:.92rem; }
.dark-table-scroll thead tr { background:#171717 !important; }
.dark-table-scroll th { color:#ffffff !important; background:#171717 !important; border-bottom:1px solid #2a2a2a !important; padding:12px 14px; text-align:left; font-weight:850; position:sticky; top:0; z-index:1; white-space:nowrap; }
.dark-table-scroll td { color:#e8e8e8 !important; background:#101010 !important; border-bottom:1px solid #242424 !important; padding:11px 14px; vertical-align:top; }
.dark-table-scroll tr:hover td { background:#151515 !important; }
[data-testid="stAlert"] { background:#111 !important; color:#fff !important; border:1px solid var(--border) !important; border-radius:14px !important; }
[data-testid="stAlert"] * { color:#fff !important; }
.streamlit-expanderHeader, [data-testid="stExpander"] details summary { background:#111 !important; color:#fff !important; border-radius:12px !important; }
.streamlit-expanderHeader *, [data-testid="stExpander"] details summary * { color:#fff !important; }
code, pre { color:#f7f7f7 !important; background:#111 !important; }
hr { border-color:var(--border) !important; }
a { color:var(--blue-hover) !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color:#bdbdbd !important; }
#MainMenu, footer { visibility:hidden; }
</style>
"""

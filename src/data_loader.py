from __future__ import annotations

import io
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def normalize_name(name: str) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "table"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    seen = {}
    cols = []
    for col in out.columns:
        c = normalize_name(col)
        if c in seen:
            seen[c] += 1
            c = f"{c}_{seen[c]}"
        else:
            seen[c] = 0
        cols.append(c)
    out.columns = cols
    return out


def _read_csv(file_obj) -> pd.DataFrame:
    return pd.read_csv(file_obj)


def _read_excel(file_obj) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(file_obj)
    return {normalize_name(sheet): normalize_columns(pd.read_excel(xls, sheet_name=sheet)) for sheet in xls.sheet_names}


def _read_json(file_obj) -> pd.DataFrame:
    data = pd.read_json(file_obj)
    if isinstance(data, pd.Series):
        data = data.to_frame("value")
    return data


def _read_sqlite(path_or_bytes, name_prefix: str = "sqlite") -> Dict[str, pd.DataFrame]:
    tables: Dict[str, pd.DataFrame] = {}
    tmp_path = None
    if isinstance(path_or_bytes, (bytes, bytearray)):
        import tempfile
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        Path(tmp_path).write_bytes(path_or_bytes)
        db_path = tmp_path
    else:
        db_path = str(path_or_bytes)

    try:
        conn = sqlite3.connect(db_path)
        table_names = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)["name"].tolist()
        for table in table_names:
            safe = table.replace('"', '""')
            df = pd.read_sql_query(f'SELECT * FROM "{safe}" LIMIT 100000', conn)
            tables[normalize_name(table)] = normalize_columns(df)
        conn.close()
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
    return tables


def load_sample_tables(base_dir: Path) -> Dict[str, pd.DataFrame]:
    sample = base_dir / "sample_data"
    tables = {}
    for path in sample.glob("*.csv"):
        tables[normalize_name(path.stem)] = normalize_columns(pd.read_csv(path))
    return tables


def load_uploaded_tables(uploaded_files) -> Dict[str, pd.DataFrame]:
    tables: Dict[str, pd.DataFrame] = {}
    for up in uploaded_files or []:
        suffix = Path(up.name).suffix.lower()
        stem = normalize_name(Path(up.name).stem)
        raw = up.getvalue()
        if suffix == ".csv":
            tables[stem] = normalize_columns(pd.read_csv(io.BytesIO(raw)))
        elif suffix in {".xlsx", ".xls"}:
            for sheet, df in _read_excel(io.BytesIO(raw)).items():
                tables[f"{stem}_{sheet}"] = df
        elif suffix == ".json":
            tables[stem] = normalize_columns(pd.read_json(io.BytesIO(raw)))
        elif suffix in {".sqlite", ".db", ".sqlite3"}:
            for k, v in _read_sqlite(raw, stem).items():
                tables[f"{stem}_{k}"] = v
    return tables


def load_sqlite_path(db_path: str) -> Dict[str, pd.DataFrame]:
    if not db_path.strip():
        return {}
    p = Path(db_path.strip()).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"SQLite database not found: {p}")
    return _read_sqlite(str(p), p.stem)


def load_sqlalchemy_tables(db_url: str, tables_csv: str, row_limit: int = 100000) -> Dict[str, pd.DataFrame]:
    if not db_url.strip() or not tables_csv.strip():
        return {}
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, pool_pre_ping=True)
    tables = {}
    for name in [x.strip() for x in tables_csv.split(",") if x.strip()]:
        # Read-only table pull. Table names cannot be parameterized in SQLAlchemy, so use a strict whitelist.
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", name):
            raise ValueError(f"Unsafe table name skipped: {name}")
        query = text(f"SELECT * FROM {name} LIMIT {int(row_limit)}")
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
        tables[normalize_name(name.split('.')[-1])] = normalize_columns(df)
    return tables


def env_db_url() -> str:
    return os.getenv("SUPPLYCHAIN_DB_URL", "").strip()

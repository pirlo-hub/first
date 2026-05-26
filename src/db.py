"""SQLite 存储：候选人 / 履历 / 客户交易 / 录用决策。"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    age INTEGER,
    education TEXT,
    total_sales_years REAL,
    source_file TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS employments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id),
    company TEXT,
    title TEXT,
    start TEXT,
    end TEXT,
    duration_months INTEGER,
    is_sales INTEGER,
    company_type TEXT
);
CREATE TABLE IF NOT EXISTS customer_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employment_id INTEGER REFERENCES employments(id),
    customer_name TEXT,
    product_category TEXT,
    product_model TEXT,
    product_brand TEXT,
    revenue TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id),
    decision TEXT,
    notes TEXT,
    post_hire_eval TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _to_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def save_extraction(data: dict, source_file: str, code: str | None = None) -> int:
    """写入一份抽取结果，返回 candidate id。"""
    init_db()
    with connect() as conn:
        cand = data.get("candidate", {}) or {}
        cur = conn.execute(
            "INSERT INTO candidates (code, age, education, total_sales_years, source_file, raw_json) "
            "VALUES (?,?,?,?,?,?)",
            (
                code,
                _to_int(cand.get("age")),
                cand.get("education"),
                _to_float(cand.get("total_sales_years")),
                source_file,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        cid = cur.lastrowid
        for emp in data.get("employments", []) or []:
            ecur = conn.execute(
                "INSERT INTO employments "
                "(candidate_id, company, title, start, end, duration_months, is_sales, company_type) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    cid,
                    emp.get("company"),
                    emp.get("title"),
                    emp.get("start"),
                    emp.get("end"),
                    _to_int(emp.get("duration_months")),
                    int(bool(emp.get("is_sales"))),
                    emp.get("company_type") or "未知",
                ),
            )
            eid = ecur.lastrowid
            for d in emp.get("customer_deals", []) or []:
                conn.execute(
                    "INSERT INTO customer_deals "
                    "(employment_id, customer_name, product_category, product_model, product_brand, revenue) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        eid,
                        d.get("customer_name"),
                        d.get("product_category"),
                        d.get("product_model"),
                        d.get("product_brand"),
                        d.get("revenue"),
                    ),
                )
        return cid


def set_decision(candidate_id: int, decision: str, notes: str | None = None) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO decisions (candidate_id, decision, notes, updated_at) "
            "VALUES (?,?,?, datetime('now','localtime')) "
            "ON CONFLICT(candidate_id) DO UPDATE SET "
            "decision=excluded.decision, notes=excluded.notes, updated_at=datetime('now','localtime')",
            (candidate_id, decision, notes),
        )


def list_candidates() -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, d.decision, d.notes FROM candidates c "
            "LEFT JOIN decisions d ON d.candidate_id = c.id ORDER BY c.id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

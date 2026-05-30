"""SQLite 存储：候选人 + 工作履历（扁平结构，每段履历存为一行）。

数据库文件名改为 library.db；旧的 data.db 不再使用，可手动删除。
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "library.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    age INTEGER,
    education TEXT,
    total_sales_years REAL,
    business_summary TEXT,
    source_file TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS employments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    seq INTEGER,
    company TEXT,
    company_type TEXT,
    title TEXT,
    start TEXT,
    end TEXT,
    is_sales INTEGER,
    customers TEXT,
    product_brands TEXT,
    product_categories TEXT,
    product_models TEXT,
    notes TEXT
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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


def _dumps(arr) -> str:
    """list/None → JSON 字符串，方便存进 TEXT 列。"""
    return json.dumps(arr or [], ensure_ascii=False)


def _loads(s) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return []


def save_extraction(data: dict, source_file: str) -> int:
    """写入一份抽取结果，返回 candidate id。"""
    init_db()
    with connect() as conn:
        cand = data.get("candidate", {}) or {}
        cur = conn.execute(
            "INSERT INTO candidates "
            "(age, education, total_sales_years, business_summary, source_file, raw_json) "
            "VALUES (?,?,?,?,?,?)",
            (
                _to_int(cand.get("age")),
                cand.get("education"),
                _to_float(cand.get("total_sales_years")),
                cand.get("business_summary"),
                source_file,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        cid = cur.lastrowid
        for i, emp in enumerate(data.get("employments", []) or []):
            conn.execute(
                "INSERT INTO employments "
                "(candidate_id, seq, company, company_type, title, start, end, is_sales, "
                " customers, product_brands, product_categories, product_models, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid, i,
                    emp.get("company"),
                    emp.get("company_type"),
                    emp.get("title"),
                    emp.get("start"),
                    emp.get("end"),
                    int(bool(emp.get("is_sales"))),
                    _dumps(emp.get("customers")),
                    _dumps(emp.get("product_brands")),
                    _dumps(emp.get("product_categories")),
                    _dumps(emp.get("product_models")),
                    emp.get("notes"),
                ),
            )
        return cid


def delete_candidate(candidate_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM employments WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))


def list_candidates() -> list[dict]:
    """返回每个候选人 + 他的所有 employments（已反序列化为 list）。"""
    init_db()
    with connect() as conn:
        cands = [dict(r) for r in conn.execute(
            "SELECT * FROM candidates ORDER BY id DESC"
        ).fetchall()]
        for c in cands:
            emps = conn.execute(
                "SELECT * FROM employments WHERE candidate_id = ? ORDER BY seq",
                (c["id"],),
            ).fetchall()
            c["employments"] = [
                {
                    **dict(e),
                    "customers": _loads(e["customers"]),
                    "product_brands": _loads(e["product_brands"]),
                    "product_categories": _loads(e["product_categories"]),
                    "product_models": _loads(e["product_models"]),
                }
                for e in emps
            ]
        return cands

"""SQLite persistence for folders, products, reference images, and image plans."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR = DATA_DIR / "uploads"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    folder_id TEXT NOT NULL REFERENCES folders(id),
    name TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT '',
    facts TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_images (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    purposes TEXT NOT NULL DEFAULT '[]',
    desc TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'success',
    sort_order INTEGER NOT NULL DEFAULT 0,
    product_relation TEXT NOT NULL DEFAULT 'unknown',
    ai_status TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS image_plans (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    image_usage TEXT NOT NULL DEFAULT '商品主图',
    ref_image_ids TEXT NOT NULL DEFAULT '[]',
    drawing_request TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    based_on_plan_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    reference_usage TEXT NOT NULL DEFAULT '[]',
    family TEXT NOT NULL DEFAULT 'main',
    design_notes TEXT NOT NULL DEFAULT '',
    open_questions TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_products_folder ON products(folder_id);
CREATE INDEX IF NOT EXISTS idx_refs_product ON ref_images(product_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_image_plans_product ON image_plans(product_id, created_at);

CREATE TABLE IF NOT EXISTS plan_runs (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES image_plans(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    planner_model TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    input_ref_ids TEXT NOT NULL DEFAULT '[]',
    rules_snapshot TEXT NOT NULL DEFAULT '[]',
    raw_output TEXT,
    design_notes TEXT,
    open_questions TEXT,
    generated_prompt TEXT,
    ref_usage_notes TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    adopted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plan_runs_plan ON plan_runs(plan_id, created_at, id);
"""


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        _seed_if_empty(conn)


def _column_names(conn, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _ensure_column(conn, table: str, col: str, ddl: str) -> None:
    if col not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


# Idempotent: only fills product_relation/ai_status when still at defaults.
_SOURCE_TO_RELATION = {
    "same": ("same_product", "unknown"),
    "other": ("other_product", "unknown"),
    "ai": ("unknown", "yes"),
}


def _migrate(conn) -> None:
    _ensure_column(
        conn, "ref_images", "product_relation", "TEXT NOT NULL DEFAULT 'unknown'"
    )
    _ensure_column(conn, "ref_images", "ai_status", "TEXT NOT NULL DEFAULT 'unknown'")
    # 1 = product_relation/ai_status are intentional (user-saved or already migrated).
    _ensure_column(conn, "ref_images", "attrs_migrated", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "image_plans", "reference_usage", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "image_plans", "family", "TEXT NOT NULL DEFAULT 'main'")
    _ensure_column(conn, "image_plans", "design_notes", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "image_plans", "open_questions", "TEXT NOT NULL DEFAULT '[]'")

    rows = conn.execute(
        """
        SELECT id, source FROM ref_images
        WHERE attrs_migrated = 0
        """
    ).fetchall()
    for row in rows:
        mapped = _SOURCE_TO_RELATION.get((row["source"] or "").strip())
        relation, ai = mapped if mapped else ("unknown", "unknown")
        conn.execute(
            """
            UPDATE ref_images
            SET product_relation = ?, ai_status = ?, attrs_migrated = 1
            WHERE id = ?
            """,
            (relation, ai, row["id"]),
        )

    plan_rows = conn.execute(
        "SELECT id, ref_image_ids, reference_usage FROM image_plans"
    ).fetchall()
    for plan in plan_rows:
        if plan["reference_usage"] and plan["reference_usage"] != "[]":
            continue
        try:
            ids = json.loads(plan["ref_image_ids"] or "[]")
        except json.JSONDecodeError:
            ids = []
        skeleton = [
            {"refImageId": rid, "roles": [], "useFor": "", "ignore": ""} for rid in ids
        ]
        conn.execute(
            "UPDATE image_plans SET reference_usage = ? WHERE id = ?",
            (json.dumps(skeleton, ensure_ascii=False), plan["id"]),
        )


def _seed_if_empty(conn) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM folders").fetchone()["c"]
    if count:
        return

    # Lightweight seed so the prototype is not empty on first boot.
    folders = [
        (new_id("f"), "摩托车配件"),
        (new_id("f"), "数码周边"),
        (new_id("f"), "汽车用品"),
        (new_id("f"), "待整理"),
    ]
    ts = now_iso()
    for fid, name in folders:
        conn.execute(
            "INSERT INTO folders (id, name, created_at) VALUES (?, ?, ?)",
            (fid, name, ts),
        )
    products = [
        (
            folders[0][0],
            "摩托车高亮辅助灯",
            "北美",
            "12V 电压，防水等级 IP67，铝合金外壳。",
        ),
        (folders[1][0], "USB-C 10合1扩展坞", "欧洲", "支持 4K@60Hz，PD 100W 充电。"),
        (folders[2][0], "汽车内饰清洁软胶", "东南亚", "无毒环保材料，不留残胶。"),
    ]
    for folder_id, name, market, facts in products:
        pid = new_id("p")
        conn.execute(
            """
            INSERT INTO products (id, folder_id, name, market, facts, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pid, folder_id, name, market, facts, ts),
        )


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(db, "DATA_DIR", data)
    monkeypatch.setattr(db, "DB_PATH", data / "app.db")
    monkeypatch.setattr(db, "UPLOAD_DIR", data / "uploads")
    monkeypatch.setattr("backend.routers.UPLOAD_DIR", data / "uploads")
    db.init_db()
    with TestClient(app) as c:
        yield c


def _create_product(client: TestClient) -> dict:
    folders = client.get("/api/folders").json()
    res = client.post(
        "/api/products",
        json={"folderId": folders[0]["id"], "name": "摩托车高亮辅助灯"},
    )
    assert res.status_code == 201
    return res.json()


def _upload_ref(client: TestClient, product_id: str, tag: str = "a") -> dict:
    res = client.post(
        f"/api/products/{product_id}/references",
        files={"file": (f"{tag}.png", tag.encode(), "image/png")},
    )
    assert res.status_code == 201
    return res.json()


def _create_plan(client: TestClient, product_id: str, **overrides) -> dict:
    payload = {
        "name": "车灯白底主图",
        "imageUsage": "商品主图",
        "drawingRequest": "简洁背景",
        "prompt": "白底",
    }
    payload.update(overrides)
    res = client.post(f"/api/products/{product_id}/plans", json=payload)
    assert res.status_code in (201, 422), res.text
    return res


def test_family_defaults_to_main(client: TestClient):
    product = _create_product(client)
    res = _create_plan(client, product["id"])
    assert res.status_code == 201
    assert res.json()["family"] == "main"
    assert res.json()["designNotes"] == ""
    assert res.json()["openQuestions"] == []


def test_family_rejects_unsupported(client: TestClient):
    product = _create_product(client)
    res = _create_plan(client, product["id"], family="scene")
    assert res.status_code == 422
    assert "family" in res.json()["detail"]


def test_family_migrates_existing_rows(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(db, "DATA_DIR", data)
    monkeypatch.setattr(db, "DB_PATH", data / "app.db")
    monkeypatch.setattr(db, "UPLOAD_DIR", data / "uploads")
    # Simulate a pre-family schema.
    data.mkdir(parents=True, exist_ok=True)
    import sqlite3

    conn = sqlite3.connect(data / "app.db")
    conn.executescript(
        """
        CREATE TABLE folders (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE products (
            id TEXT PRIMARY KEY, folder_id TEXT NOT NULL, name TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT '', facts TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
        );
        CREATE TABLE ref_images (
            id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, product_id TEXT NOT NULL,
            url TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', purposes TEXT NOT NULL DEFAULT '[]',
            desc TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'success',
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE image_plans (
            id TEXT PRIMARY KEY, product_id TEXT NOT NULL, name TEXT NOT NULL,
            image_usage TEXT NOT NULL DEFAULT '商品主图', ref_image_ids TEXT NOT NULL DEFAULT '[]',
            drawing_request TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft', based_on_plan_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, confirmed_at TEXT
        );
        INSERT INTO folders VALUES ('f1', 'x', '2026-01-01 00:00:00');
        INSERT INTO products VALUES ('p1', 'f1', 'y', '', '', '2026-01-01 00:00:00');
        INSERT INTO image_plans VALUES (
            'pl1', 'p1', 'old', '商品主图', '[]', '', '', 'draft',
            NULL, '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL
        );
        """
    )
    conn.commit()
    conn.close()

    db.init_db()
    with TestClient(app) as c:
        res = c.get("/api/plans/pl1")
        assert res.status_code == 200
        assert res.json()["family"] == "main"


def test_family_patch_updates(client: TestClient):
    product = _create_product(client)
    plan = _create_plan(client, product["id"]).json()
    res = client.patch(f"/api/plans/{plan['id']}", json={"family": "main"})
    assert res.status_code == 200
    assert res.json()["family"] == "main"
    bad = client.patch(f"/api/plans/{plan['id']}", json={"family": "wear"})
    assert bad.status_code == 422


def _usage_primary_first(client: TestClient, product_id: str) -> list[dict]:
    refs = [
        _upload_ref(client, product_id, "a"),
        _upload_ref(client, product_id, "b"),
    ]
    return refs, [
        {
            "refImageId": refs[0]["id"],
            "roles": ["primary"],
            "useFor": "灯身",
            "ignore": "背景",
        },
        {
            "refImageId": refs[1]["id"],
            "roles": ["detail"],
            "useFor": "接口",
            "ignore": "",
        },
    ]


def test_load_plan_case_matches_fixture_shape(client: TestClient):
    from backend.db import connect
    from backend.skill_preview import validate_case
    from backend.skill_preview.loader import load_plan_case

    product = _create_product(client)
    refs, usage = _usage_primary_first(client, product["id"])
    plan = _create_plan(client, product["id"], referenceUsage=usage).json()
    with connect() as conn:
        case = load_plan_case(conn, plan["id"])
    validate_case(case)
    assert case["family"] == "main"
    assert case["product"]["name"] == "摩托车高亮辅助灯"
    assert case["plan"]["id"] == plan["id"]
    assert [r["id"] for r in case["references"]] == [r["id"] for r in refs]
    assert case["referenceUsage"][0]["refImageId"] == refs[0]["id"]


def test_parse_plan_output_requires_prompt():
    from backend.planner import PlannerError, parse_plan_output

    with pytest.raises(PlannerError, match="prompt"):
        parse_plan_output('{"designNotes": "x", "openQuestions": []}')
    parsed = parse_plan_output(
        '{"designNotes": "d", "prompt": "p", "openQuestions": ["q"], "refUsageNotes": "r"}'
    )
    assert parsed["prompt"] == "p"
    assert parsed["openQuestions"] == ["q"]


def test_skill_run_missing_primary_records_failed(client: TestClient):
    product = _create_product(client)
    ref = _upload_ref(client, product["id"], "a")
    plan = _create_plan(
        client,
        product["id"],
        referenceUsage=[
            {"refImageId": ref["id"], "roles": ["detail"], "useFor": "x", "ignore": ""},
        ],
    ).json()
    res = client.post(f"/api/plans/{plan['id']}/skill-run")
    assert res.status_code == 200
    run = res.json()
    assert run["status"] == "failed"
    assert "missing_primary" in run["error"]
    # 草稿字段不被污染
    detail = client.get(f"/api/plans/{plan['id']}").json()
    assert detail["prompt"] == "白底"
    assert detail["status"] == "draft"


def test_skill_run_success_and_adopt(client: TestClient, monkeypatch, tmp_path):
    from backend import db

    upload = tmp_path / "uploads"
    upload.mkdir()
    (upload / "a.png").write_bytes(b"img-a")
    (upload / "b.png").write_bytes(b"img-b")
    monkeypatch.setattr(db, "UPLOAD_DIR", upload)
    monkeypatch.setattr("backend.routers.UPLOAD_DIR", upload)

    def fake_run_planner(messages, *, config=None, timeout=120.0):
        assert isinstance(messages[1]["content"], list)
        kinds = [p["type"] for p in messages[1]["content"]]
        assert kinds[0] == "text"
        assert kinds[1:] == ["image_url", "image_url"]
        return (
            '{"designNotes": "白底依据 facts", "prompt": "生成用提示词",'
            ' "openQuestions": ["是否含支架"], "refUsageNotes": "A主体"}'
        )

    monkeypatch.setattr("backend.routers.run_planner", fake_run_planner)
    monkeypatch.setenv("PLANNER_MODEL", "test-model")
    monkeypatch.setenv("PLANNER_BASE_URL", "http://localhost:9")
    monkeypatch.setenv("PLANNER_API_KEY", "k")

    product = _create_product(client)
    # 上传真实文件名需要与 url 对应；upload_reference 生成 /uploads/{rid}.png
    refs = [
        _upload_ref(client, product["id"], "a"),
        _upload_ref(client, product["id"], "b"),
    ]
    for ref in refs:
        url = ref["url"]  # /uploads/{id}.png
        name = url.rsplit("/", 1)[-1]
        (upload / name).write_bytes(b"img-" + ref["id"].encode())

    plan = _create_plan(
        client,
        product["id"],
        referenceUsage=[
            {
                "refImageId": refs[0]["id"],
                "roles": ["primary"],
                "useFor": "灯身",
                "ignore": "背景",
            },
            {
                "refImageId": refs[1]["id"],
                "roles": ["detail"],
                "useFor": "接口",
                "ignore": "",
            },
        ],
    ).json()

    res = client.post(f"/api/plans/{plan['id']}/skill-run")
    assert res.status_code == 200
    run = res.json()
    assert run["status"] == "success"
    assert run["generatedPrompt"] == "生成用提示词"
    assert run["openQuestions"] == ["是否含支架"]
    assert run["plannerModel"] == "test-model"
    assert run["rulesSnapshot"] and run["rulesSnapshot"][0]["sha256"]
    assert run["adoptedAt"] is None

    # 不采纳则方案字段不变
    detail = client.get(f"/api/plans/{plan['id']}").json()
    assert detail["prompt"] == "白底"
    assert detail["status"] == "draft"

    adopted = client.post(f"/api/plans/{plan['id']}/adopt", json={"runId": run["id"]})
    assert adopted.status_code == 200
    body = adopted.json()
    assert body["prompt"] == "生成用提示词"
    assert body["designNotes"] == "白底依据 facts"
    assert body["openQuestions"] == ["是否含支架"]
    assert body["status"] == "draft"

    runs = client.get(f"/api/plans/{plan['id']}/runs").json()
    assert runs[0]["id"] == run["id"]
    assert runs[0]["adoptedAt"]


def test_skill_run_parse_failure_keeps_draft(client: TestClient, monkeypatch):
    from backend.planner import PlannerError

    def bad_planner(messages, *, config=None, timeout=120.0):
        raise PlannerError("解析失败", raw_output="not-json")

    monkeypatch.setattr("backend.routers.run_planner", bad_planner)
    monkeypatch.setattr(
        "backend.routers.load_config",
        lambda: {"model": "m", "base_url": "http://x", "api_key": "k"},
    )

    product = _create_product(client)
    _refs, usage = _usage_primary_first(client, product["id"])
    plan = _create_plan(client, product["id"], referenceUsage=usage).json()
    res = client.post(f"/api/plans/{plan['id']}/skill-run")
    assert res.status_code == 200
    run = res.json()
    assert run["status"] == "failed"
    assert run["rawOutput"] == "not-json"
    assert run["error"]
    detail = client.get(f"/api/plans/{plan['id']}").json()
    assert detail["prompt"] == "白底"


def test_now_iso_has_seconds():
    from backend.db import now_iso

    assert len(now_iso()) >= 19
    assert now_iso()[16] == ":"  # HH:MM:SS has second colon at index 16


def test_run_snapshot_survives_rule_change(client: TestClient, monkeypatch):
    import hashlib

    def fake_run_planner(messages, *, config=None, timeout=120.0):
        return '{"designNotes": "d", "prompt": "p1", "openQuestions": []}'

    monkeypatch.setattr("backend.routers.run_planner", fake_run_planner)
    monkeypatch.setattr(
        "backend.routers.load_config",
        lambda: {"model": "m", "base_url": "http://x", "api_key": "k"},
    )

    product = _create_product(client)
    _refs, usage = _usage_primary_first(client, product["id"])
    plan = _create_plan(client, product["id"], referenceUsage=usage).json()
    run = client.post(f"/api/plans/{plan['id']}/skill-run").json()
    assert run["status"] == "success"
    saved_system = run["systemPrompt"]
    saved_hash = run["rulesSnapshot"][0]["sha256"]

    from backend.skill_preview.loader import SKILLS_ROOT

    main_md = SKILLS_ROOT / "families" / "main.md"
    original = main_md.read_text(encoding="utf-8")
    try:
        main_md.write_text(original + "\n<!-- changed -->\n", encoding="utf-8")
        runs = client.get(f"/api/plans/{plan['id']}/runs").json()
        assert runs[0]["systemPrompt"] == saved_system
        assert runs[0]["rulesSnapshot"][0]["sha256"] == saved_hash
        assert hashlib.sha256(main_md.read_bytes()).hexdigest() != saved_hash
    finally:
        main_md.write_text(original, encoding="utf-8")

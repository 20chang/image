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


def _create_product(client: TestClient, name: str = "H4 车灯") -> dict:
    folders = client.get("/api/folders").json()
    res = client.post(
        "/api/products",
        json={"folderId": folders[0]["id"], "name": name},
    )
    assert res.status_code == 201
    return res.json()


def _upload_ref(client: TestClient, product_id: str, tag: bytes) -> dict:
    res = client.post(
        f"/api/products/{product_id}/references",
        files={"file": (f"{tag.decode()}.png", tag, "image/png")},
    )
    assert res.status_code == 201
    return res.json()


def _patch_meta(client: TestClient, ref_id: str, **fields) -> dict:
    res = client.patch(f"/api/references/{ref_id}", json=fields)
    assert res.status_code == 200
    return res.json()


def test_ref_image_relation_and_ai_status_roundtrip(client: TestClient):
    product = _create_product(client)
    ref = _upload_ref(client, product["id"], b"overall")

    out = _patch_meta(
        client,
        ref["id"],
        source="",
        purposes=[],
        desc="整体图",
        productRelation="same_product",
        aiStatus="no",
    )
    assert out["productRelation"] == "same_product"
    assert out["aiStatus"] == "no"
    assert out["desc"] == "整体图"

    listed = client.get(f"/api/products/{product['id']}/references").json()
    assert listed[0]["productRelation"] == "same_product"
    assert listed[0]["aiStatus"] == "no"

    unknown = _patch_meta(
        client,
        ref["id"],
        source="",
        purposes=[],
        desc="",
        productRelation="unknown",
        aiStatus="unknown",
    )
    assert unknown["productRelation"] == "unknown"
    assert unknown["aiStatus"] == "unknown"


def test_reference_usage_roles_and_summary(client: TestClient):
    product = _create_product(client)
    overall = _upload_ref(client, product["id"], b"overall")
    detail = _upload_ref(client, product["id"], b"detail")
    poster = _upload_ref(client, product["id"], b"poster")

    created = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "车灯白底主图",
            "referenceUsage": [
                {
                    "refImageId": overall["id"],
                    "roles": ["primary"],
                    "useFor": "灯身外观",
                    "ignore": "背景",
                },
                {
                    "refImageId": detail["id"],
                    "roles": ["detail"],
                    "useFor": "接口",
                    "ignore": "",
                },
                {
                    "refImageId": poster["id"],
                    "roles": ["composition"],
                    "useFor": "",
                    "ignore": "其中的商品、文字和 Logo",
                },
            ],
        },
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["refImageIds"] == [overall["id"], detail["id"], poster["id"]]
    assert [u["roles"] for u in plan["referenceUsage"]] == [
        ["primary"],
        ["detail"],
        ["composition"],
    ]
    summary = plan["usageSummary"]
    assert "A图提供灯身外观" in summary
    assert "B图补充接口" in summary
    assert "C图只参考构图" in summary
    assert "忽略其中的商品、文字和 Logo" in summary


def test_same_image_different_roles_per_plan(client: TestClient):
    product = _create_product(client)
    img = _upload_ref(client, product["id"], b"shared")

    plan_a = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "方案 A",
            "referenceUsage": [
                {"refImageId": img["id"], "roles": ["primary"], "useFor": "外观"}
            ],
        },
    ).json()
    plan_b = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "方案 B",
            "referenceUsage": [
                {"refImageId": img["id"], "roles": ["composition"], "useFor": ""}
            ],
        },
    ).json()
    assert plan_a["referenceUsage"][0]["roles"] == ["primary"]
    assert plan_b["referenceUsage"][0]["roles"] == ["composition"]
    assert plan_a["id"] != plan_b["id"]


def test_sort_order_does_not_rewrite_plan(client: TestClient):
    product = _create_product(client)
    a = _upload_ref(client, product["id"], b"aa")
    b = _upload_ref(client, product["id"], b"bb")
    plan = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "顺序固定",
            "referenceUsage": [
                {"refImageId": b["id"], "roles": ["primary"]},
                {"refImageId": a["id"], "roles": ["detail"]},
            ],
        },
    ).json()
    assert plan["refImageIds"] == [b["id"], a["id"]]

    client.post(f"/api/references/{a['id']}/reorder", json={"direction": "up"})
    reread = client.get(f"/api/plans/{plan['id']}").json()
    assert reread["refImageIds"] == [b["id"], a["id"]]
    assert reread["referenceUsage"][0]["refImageId"] == b["id"]
    assert reread["referenceUsage"][1]["refImageId"] == a["id"]


def test_invalid_usage_rejected(client: TestClient):
    product = _create_product(client)
    other = _create_product(client, "他品")
    own = _upload_ref(client, product["id"], b"own")
    foreign = _upload_ref(client, other["id"], b"foreign")

    bad_enum = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "枚举",
            "referenceUsage": [{"refImageId": own["id"], "roles": ["hero"]}],
        },
    )
    assert bad_enum.status_code == 422

    dup = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "重复",
            "referenceUsage": [
                {"refImageId": own["id"], "roles": ["primary"]},
                {"refImageId": own["id"], "roles": ["detail"]},
            ],
        },
    )
    assert dup.status_code == 422

    two_primary = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "双主体",
            "referenceUsage": [
                {"refImageId": own["id"], "roles": ["primary"]},
                {"refImageId": foreign["id"], "roles": ["primary"]},
            ],
        },
    )
    assert two_primary.status_code == 422

    foreign_ref = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "越权",
            "referenceUsage": [{"refImageId": foreign["id"], "roles": ["detail"]}],
        },
    )
    assert foreign_ref.status_code == 422


def test_confirm_requires_roles_for_selected(client: TestClient):
    product = _create_product(client)
    img = _upload_ref(client, product["id"], b"x")
    plan = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "待补角色",
            "referenceUsage": [{"refImageId": img["id"], "roles": []}],
        },
    ).json()
    blocked = client.post(f"/api/plans/{plan['id']}/confirm")
    assert blocked.status_code == 422

    patched = client.patch(
        f"/api/plans/{plan['id']}",
        json={
            "referenceUsage": [
                {"refImageId": img["id"], "roles": ["primary"], "useFor": "外观"}
            ]
        },
    )
    assert patched.status_code == 200
    ok = client.post(f"/api/plans/{plan['id']}/confirm")
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"
    assert ok.json()["referenceUsage"][0]["roles"] == ["primary"]


def test_delete_reference_blocked_when_referenced(client: TestClient):
    product = _create_product(client)
    img = _upload_ref(client, product["id"], b"used")
    plan = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "占用",
            "referenceUsage": [{"refImageId": img["id"], "roles": ["primary"]}],
        },
    ).json()
    res = client.delete(f"/api/references/{img['id']}")
    assert res.status_code == 409

    client.patch(
        f"/api/plans/{plan['id']}",
        json={"referenceUsage": []},
    )
    ok = client.delete(f"/api/references/{img['id']}")
    assert ok.status_code == 204


def test_legacy_source_migrates_and_plans_get_skeleton(
    client: TestClient, tmp_path, monkeypatch
):
    product = _create_product(client)
    ref_same = _upload_ref(client, product["id"], b"same")
    ref_ai = _upload_ref(client, product["id"], b"ai")
    _patch_meta(client, ref_same["id"], source="same", purposes=["overall"], desc="")
    _patch_meta(client, ref_ai["id"], source="ai", purposes=["composition"], desc="")

    plan = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "旧式", "refImageIds": [ref_same["id"], ref_ai["id"]]},
    ).json()
    assert [u["roles"] for u in plan["referenceUsage"]] == [[], []]

    # Simulate pre-migration DB by clearing new columns, then re-init.
    import sqlite3

    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "UPDATE ref_images SET product_relation='unknown', ai_status='unknown', attrs_migrated=0"
    )
    conn.commit()
    conn.close()

    db.init_db()
    with TestClient(app) as fresh:
        listed = fresh.get(f"/api/products/{product['id']}/references").json()
        by_id = {r["id"]: r for r in listed}
        assert by_id[ref_same["id"]]["productRelation"] == "same_product"
        assert by_id[ref_same["id"]]["aiStatus"] == "unknown"
        assert by_id[ref_ai["id"]]["productRelation"] == "unknown"
        assert by_id[ref_ai["id"]]["aiStatus"] == "yes"

        reread = fresh.get(f"/api/plans/{plan['id']}").json()
        assert reread["refImageIds"] == [ref_same["id"], ref_ai["id"]]
        assert [u["refImageId"] for u in reread["referenceUsage"]] == [
            ref_same["id"],
            ref_ai["id"],
        ]
        # Second init must not clobber already-mapped values.
        db.init_db()
        with TestClient(app) as again:
            again_listed = again.get(f"/api/products/{product['id']}/references").json()
            again_by = {r["id"]: r for r in again_listed}
            assert again_by[ref_same["id"]]["productRelation"] == "same_product"
            assert again_by[ref_ai["id"]]["aiStatus"] == "yes"


def test_user_saved_unknown_survives_migration(client: TestClient):
    product = _create_product(client)
    ref = _upload_ref(client, product["id"], b"mixed")
    _patch_meta(
        client,
        ref["id"],
        source="same",
        purposes=[],
        desc="",
        productRelation="unknown",
        aiStatus="unknown",
    )
    db.init_db()
    with TestClient(app) as fresh:
        listed = fresh.get(f"/api/products/{product['id']}/references").json()
        row = next(r for r in listed if r["id"] == ref["id"])
        assert row["productRelation"] == "unknown"
        assert row["aiStatus"] == "unknown"


def test_duplicate_ref_image_ids_rejected(client: TestClient):
    product = _create_product(client)
    img = _upload_ref(client, product["id"], b"one")
    res = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "重复ID", "refImageIds": [img["id"], img["id"]]},
    )
    assert res.status_code == 422

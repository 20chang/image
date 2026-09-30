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


def _upload_ref(client: TestClient, product_id: str, tag: bytes = b"png") -> dict:
    res = client.post(
        f"/api/products/{product_id}/references",
        files={"file": (f"{tag.decode()}.png", tag, "image/png")},
    )
    assert res.status_code == 201
    return res.json()


def test_plan_lifecycle_survives_restart(client: TestClient, tmp_path, monkeypatch):
    product = _create_product(client)
    ref_a = _upload_ref(client, product["id"], b"aa")
    ref_b = _upload_ref(client, product["id"], b"bb")
    ref_ids = [ref_a["id"], ref_b["id"]]

    created = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "车灯白底主图",
            "imageUsage": "商品主图",
            "refImageIds": ref_ids,
            "drawingRequest": "简洁背景，完整展示商品",
            "prompt": "白底，正面 45 度，突出灯体轮廓",
        },
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["status"] == "draft"
    assert plan["productId"] == product["id"]
    assert plan["refImageIds"] == ref_ids
    assert plan["id"].startswith("pl")

    updated = client.patch(
        f"/api/plans/{plan['id']}",
        json={
            "prompt": "白底，正面 45 度，突出灯体轮廓与接口细节",
            "referenceUsage": [
                {
                    "refImageId": ref_ids[0],
                    "roles": ["primary"],
                    "useFor": "灯身外观",
                    "ignore": "背景",
                },
                {
                    "refImageId": ref_ids[1],
                    "roles": ["detail"],
                    "useFor": "接口",
                    "ignore": "",
                },
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["prompt"].endswith("接口细节")
    assert updated.json()["drawingRequest"] == "简洁背景，完整展示商品"

    # Simulate backend restart: new TestClient over the same DB file.
    with TestClient(app) as fresh:
        detail = fresh.get(f"/api/plans/{plan['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["name"] == "车灯白底主图"
        assert body["refImageIds"] == ref_ids
        assert body["prompt"].endswith("接口细节")

        confirmed = fresh.post(f"/api/plans/{plan['id']}/confirm")
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"
        assert confirmed.json()["confirmedAt"]

        again = fresh.get(f"/api/plans/{plan['id']}")
        assert again.status_code == 200
        assert again.json()["status"] == "confirmed"

        listed = fresh.get(f"/api/products/{product['id']}/plans")
        assert [p["id"] for p in listed.json()] == [plan["id"]]


def test_reject_foreign_ref_image_and_bad_based_on(client: TestClient):
    product = _create_product(client)
    other = _create_product(client)
    foreign_ref = _upload_ref(client, other["id"], b"x")
    own_ref = _upload_ref(client, product["id"], b"y")

    bad_ref = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "A", "refImageIds": [foreign_ref["id"]]},
    )
    assert bad_ref.status_code == 422

    src = client.post(
        f"/api/products/{product['id']}/plans",
        json={
            "name": "源",
            "refImageIds": [own_ref["id"]],
            "referenceUsage": [
                {"refImageId": own_ref["id"], "roles": ["primary"], "useFor": "主体"}
            ],
        },
    )
    assert src.status_code == 201

    bad_based = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "B", "basedOnPlanId": "pl-missing"},
    )
    assert bad_based.status_code == 422

    foreign_plan = client.post(
        f"/api/products/{other['id']}/plans",
        json={"name": "他品"},
    )
    assert foreign_plan.status_code == 201
    bad_based2 = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "C", "basedOnPlanId": foreign_plan.json()["id"]},
    )
    assert bad_based2.status_code == 422

    ok = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "D", "basedOnPlanId": src.json()["id"]},
    )
    assert ok.status_code == 201
    assert ok.json()["basedOnPlanId"] == src.json()["id"]


def test_confirmed_plan_is_immutable(client: TestClient):
    product = _create_product(client)
    plan = client.post(
        f"/api/products/{product['id']}/plans",
        json={"name": "锁定", "prompt": "v1"},
    ).json()
    assert client.post(f"/api/plans/{plan['id']}/confirm").status_code == 200

    patch = client.patch(f"/api/plans/{plan['id']}", json={"prompt": "v2"})
    assert patch.status_code == 409

    reconfirm = client.post(f"/api/plans/{plan['id']}/confirm")
    assert reconfirm.status_code == 409

    detail = client.get(f"/api/plans/{plan['id']}").json()
    assert detail["prompt"] == "v1"
    assert detail["status"] == "confirmed"


def test_unknown_ids_are_404(client: TestClient):
    assert client.get("/api/plans/plnope").status_code == 404
    assert client.get("/api/products/pnope/plans").status_code == 404
    assert client.post("/api/plans/plnope/confirm").status_code == 404
    assert (
        client.post("/api/products/pnope/plans", json={"name": "x"}).status_code == 404
    )

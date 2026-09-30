"""Live smoke for ref-image-roles acceptance (run while backend is up)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api"


def req(method: str, path: str, body=None, raw=None):
    data = None
    headers = {}
    if raw is not None:
        data = raw
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload) if payload else None
        except json.JSONDecodeError:
            return e.code, payload


def multipart(path: str, filename: str, content: bytes):
    boundary = "----smokeBoundary7MA4YWxkTrZu0gW"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    r = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(r) as resp:
        return resp.status, json.loads(resp.read())


def main() -> int:
    st, folders = req("GET", "/folders")
    assert st == 200 and folders, "folders"
    st, product = req(
        "POST",
        "/products",
        {"folderId": folders[0]["id"], "name": "H4 车灯冒烟"},
    )
    assert st == 201, product
    pid = product["id"]

    tags = [
        ("overall.png", b"\x89PNG-Overall"),
        ("detail.png", b"\x89PNG-Detail"),
        ("poster.png", b"\x89PNG-Poster"),
    ]
    refs = []
    for name, blob in tags:
        st, ref = multipart(f"/products/{pid}/references", name, blob)
        assert st == 201, ref
        refs.append(ref)
    overall, detail, poster = refs

    st, meta = req(
        "PATCH",
        f"/references/{overall['id']}",
        {
            "source": "",
            "purposes": [],
            "desc": "商品整体图",
            "productRelation": "same_product",
            "aiStatus": "no",
        },
    )
    assert st == 200 and meta["productRelation"] == "same_product", meta
    req(
        "PATCH",
        f"/references/{detail['id']}",
        {
            "source": "",
            "purposes": [],
            "desc": "接口特写",
            "productRelation": "same_product",
            "aiStatus": "no",
        },
    )
    req(
        "PATCH",
        f"/references/{poster['id']}",
        {
            "source": "",
            "purposes": [],
            "desc": "竞品海报",
            "productRelation": "other_product",
            "aiStatus": "yes",
        },
    )

    st, plan_a = req(
        "POST",
        f"/products/{pid}/plans",
        {
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
    assert st == 201, plan_a
    print("A summary:", plan_a["usageSummary"])
    assert "A图提供灯身外观" in plan_a["usageSummary"]
    assert plan_a["refImageIds"] == [overall["id"], detail["id"], poster["id"]]

    st, plan_b = req(
        "POST",
        f"/products/{pid}/plans",
        {
            "name": "构图试验",
            "referenceUsage": [
                {
                    "refImageId": poster["id"],
                    "roles": ["primary"],
                    "useFor": "海报布局",
                },
            ],
        },
    )
    assert st == 201, plan_b
    assert plan_b["referenceUsage"][0]["roles"] == ["primary"]
    assert plan_a["referenceUsage"][2]["roles"] == ["composition"]

    # Reorder materials — plan order must not change
    st, _ = req("POST", f"/references/{overall['id']}/reorder", {"direction": "down"})
    st, reread = req("GET", f"/plans/{plan_a['id']}")
    assert reread["refImageIds"] == [overall["id"], detail["id"], poster["id"]], reread[
        "refImageIds"
    ]

    # Illegal: foreign ref / duplicate / two primaries
    st, other = req(
        "POST", "/products", {"folderId": folders[0]["id"], "name": "他品冒烟"}
    )
    st, foreign = multipart(f"/products/{other['id']}/references", "x.png", b"x")
    st, bad = req(
        "POST",
        f"/products/{pid}/plans",
        {
            "name": "越权",
            "referenceUsage": [{"refImageId": foreign["id"], "roles": ["detail"]}],
        },
    )
    assert st == 422, bad
    st, bad2 = req(
        "POST",
        f"/products/{pid}/plans",
        {
            "name": "双主体",
            "referenceUsage": [
                {"refImageId": overall["id"], "roles": ["primary"]},
                {"refImageId": detail["id"], "roles": ["primary"]},
            ],
        },
    )
    assert st == 422, bad2

    # Delete blocked while referenced
    st, err = req("DELETE", f"/references/{poster['id']}")
    assert st == 409, err

    # Confirm requires roles
    st, plan_c = req(
        "POST",
        f"/products/{pid}/plans",
        {
            "name": "缺角色",
            "referenceUsage": [{"refImageId": overall["id"], "roles": []}],
        },
    )
    st, err = req("POST", f"/plans/{plan_c['id']}/confirm")
    assert st == 422, err

    st, conf = req("POST", f"/plans/{plan_a['id']}/confirm")
    assert st == 200 and conf["status"] == "confirmed", conf
    st, frozen = req("PATCH", f"/plans/{plan_a['id']}", {"prompt": "x"})
    assert st == 409, frozen

    print(
        "SMOKE OK",
        json.dumps(
            {"product": pid, "planA": plan_a["id"], "planB": plan_b["id"]},
            ensure_ascii=False,
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

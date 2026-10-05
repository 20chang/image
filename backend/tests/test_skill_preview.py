from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.skill_preview import assemble_request, load_case, validate_case
from backend.skill_preview.loader import SkillPreviewError

CASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "cases"
    / "car-light-main.case.json"
)


def _user_text(result: dict) -> str:
    content = result["model_request"]["messages"][1]["content"]
    if isinstance(content, str):
        return content
    return "\n".join(
        p.get("text", "")
        for p in content
        if isinstance(p, dict) and p.get("type") == "text"
    )


def _image_blocks(result: dict) -> list[dict]:
    content = result["model_request"]["messages"][1]["content"]
    if isinstance(content, str):
        return []
    return [p for p in content if isinstance(p, dict) and p.get("type") == "image_url"]


def _base_case() -> dict:
    return {
        "family": "main",
        "product": {
            "id": "p1",
            "name": "LED 车灯 H7 55W",
            "market": "国内电商",
            "facts": "H7 灯座，铝合金灯身带散热鳍片。",
        },
        "plan": {
            "id": "pl1",
            "name": "车灯主图",
            "imageUsage": "商品主图",
            "drawingRequest": "白底主图",
            "prompt": "",
        },
        "references": [
            {
                "id": "ref-A",
                "url": "/static/fixtures/a.jpg",
                "productRelation": "same_product",
                "aiStatus": "no",
                "desc": "整体图备注-甲",
            },
            {
                "id": "ref-B",
                "url": "/static/fixtures/b.jpg",
                "productRelation": "same_product",
                "aiStatus": "no",
                "desc": "接口特写备注-乙",
            },
            {
                "id": "ref-C",
                "url": "/static/fixtures/c.jpg",
                "productRelation": "other_product",
                "aiStatus": "unknown",
                "desc": "海报备注-丙",
            },
        ],
        "referenceUsage": [
            {
                "refImageId": "ref-A",
                "roles": ["primary"],
                "useFor": "灯身外观",
                "ignore": "背景",
            },
            {
                "refImageId": "ref-B",
                "roles": ["detail"],
                "useFor": "接口形状",
                "ignore": "",
            },
            {
                "refImageId": "ref-C",
                "roles": ["composition"],
                "useFor": "构图",
                "ignore": "商品文字",
            },
        ],
    }


def _write_case(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------- desc / url 进入请求预览 ----------


def test_desc_and_url_enter_request(tmp_path: Path) -> None:
    data = _base_case()
    data["references"][0]["desc"] = "改过的整体图备注"
    data["references"][0]["url"] = "https://cdn.example.com/a-new.jpg"
    result = assemble_request("main", str(_write_case(tmp_path, data)))
    user = _user_text(result)
    assert "改过的整体图备注" in user
    assert "https://cdn.example.com/a-new.jpg" in user
    imgs = {i["refImageId"]: i for i in result["image_inputs"]}
    assert imgs["ref-A"]["url"] == "https://cdn.example.com/a-new.jpg"
    assert imgs["ref-A"]["status"] == "已提供地址（图片内容待解析）"


def test_fixture_url_marked_as_placeholder(tmp_path: Path) -> None:
    result = assemble_request("main", str(_write_case(tmp_path, _base_case())))
    imgs = {i["refImageId"]: i for i in result["image_inputs"]}
    assert "测试占位" in imgs["ref-A"]["status"]
    user = _user_text(result)
    assert "不代表模型已收到图片" in user
    status = result["assembly_status"]
    assert status["rules_loaded"] is True
    assert status["request_assembled"] is True
    assert status["images_resolved"] is False
    assert status["model_called"] is False
    assert status["image_generated"] is False


# ---------- 重排后身份与内容对应 ----------


def test_reorder_keeps_identity_and_content(tmp_path: Path) -> None:
    data = _base_case()
    data["referenceUsage"] = [
        {
            "refImageId": "ref-C",
            "roles": ["composition"],
            "useFor": "构图",
            "ignore": "商品文字",
        },
        {
            "refImageId": "ref-A",
            "roles": ["primary"],
            "useFor": "灯身外观",
            "ignore": "背景",
        },
    ]
    result = assemble_request("main", str(_write_case(tmp_path, data)))
    order = result["ref_order"]
    assert [o["refImageId"] for o in order] == ["ref-C", "ref-A"]
    assert [o["label"] for o in order] == ["A", "B"]

    user = _user_text(result)
    # A 现在是 ref-C，其备注与 URL 必须跟着走
    a_pos = user.index("A（ref-C）")
    c_pos = user.index("海报备注-丙")
    assert a_pos < c_pos
    imgs = result["image_inputs"]
    assert imgs[0]["refImageId"] == "ref-C"
    assert imgs[0]["url"].endswith("c.jpg")
    assert imgs[1]["refImageId"] == "ref-A"
    assert imgs[1]["url"].endswith("a.jpg")
    # 文字说明与图片输入顺序一致
    user_img_section = user.split("## 参考图图片输入")[1]
    assert user_img_section.index("A（ref-C）") < user_img_section.index("B（ref-A）")


def test_desc_change_changes_request(tmp_path: Path) -> None:
    data1 = _base_case()
    r1 = assemble_request("main", str(_write_case(tmp_path, data1)))
    data2 = _base_case()
    data2["references"][1]["desc"] = "完全不同的备注"
    path = tmp_path / "case2.json"
    path.write_text(json.dumps(data2, ensure_ascii=False), encoding="utf-8")
    r2 = assemble_request("main", str(path))
    assert _user_text(r1) != _user_text(r2)
    assert "完全不同的备注" in _user_text(r2)


# ---------- 拒绝非法输入 ----------


def test_duplicate_reference_id_rejected(tmp_path: Path) -> None:
    data = _base_case()
    data["references"].append(dict(data["references"][0]))
    with pytest.raises(SkillPreviewError, match="重复"):
        validate_case(data)


def test_duplicate_usage_ref_rejected(tmp_path: Path) -> None:
    data = _base_case()
    data["referenceUsage"].append(dict(data["referenceUsage"][0]))
    with pytest.raises(SkillPreviewError, match="重复引用"):
        validate_case(data)


def test_nonexistent_ref_rejected() -> None:
    data = _base_case()
    data["referenceUsage"][0]["refImageId"] = "ref-ZZZ"
    with pytest.raises(SkillPreviewError, match="不存在"):
        validate_case(data)


def test_illegal_role_rejected() -> None:
    data = _base_case()
    data["referenceUsage"][0]["roles"] = ["hero"]
    with pytest.raises(SkillPreviewError, match="非法角色"):
        validate_case(data)


def test_multiple_primary_rejected() -> None:
    data = _base_case()
    data["referenceUsage"][1]["roles"] = ["primary", "detail"]
    with pytest.raises(SkillPreviewError, match="primary"):
        validate_case(data)


# ---------- 字段类型错误，指出位置 ----------


def test_product_type_error_names_field() -> None:
    data = _base_case()
    data["product"] = "not-a-dict"
    with pytest.raises(SkillPreviewError, match=r"product 必须是对象"):
        validate_case(data)


def test_plan_name_type_error_names_field() -> None:
    data = _base_case()
    data["plan"]["name"] = 123
    with pytest.raises(SkillPreviewError, match=r"plan\.name"):
        validate_case(data)


def test_references_type_error_names_field() -> None:
    data = _base_case()
    data["references"] = {"a": 1}
    with pytest.raises(SkillPreviewError, match=r"references 必须是数组"):
        validate_case(data)


def test_reference_usage_type_error_names_field() -> None:
    data = _base_case()
    data["referenceUsage"] = "nope"
    with pytest.raises(SkillPreviewError, match=r"referenceUsage 必须是数组"):
        validate_case(data)


def test_usage_ref_id_type_error_names_index() -> None:
    data = _base_case()
    data["referenceUsage"][1]["refImageId"] = 42
    with pytest.raises(SkillPreviewError, match=r"referenceUsage\[1\]\.refImageId"):
        validate_case(data)


def test_roles_type_error_names_index() -> None:
    data = _base_case()
    data["referenceUsage"][0]["roles"] = "primary"
    with pytest.raises(SkillPreviewError, match=r"referenceUsage\[0\]\.roles"):
        validate_case(data)


def test_roles_non_string_element_rejected() -> None:
    data = _base_case()
    data["referenceUsage"][0]["roles"] = [{}]
    with pytest.raises(
        SkillPreviewError, match=r"referenceUsage\[0\]\.roles\[0\] 必须是字符串"
    ):
        validate_case(data)


def test_product_relation_wrong_type_rejected() -> None:
    data = _base_case()
    data["references"][0]["productRelation"] = []
    with pytest.raises(
        SkillPreviewError, match=r"references\[0\]\.productRelation 必须是字符串"
    ):
        validate_case(data)


def test_ai_status_wrong_type_rejected() -> None:
    data = _base_case()
    data["references"][0]["aiStatus"] = {}
    with pytest.raises(
        SkillPreviewError, match=r"references\[0\]\.aiStatus 必须是字符串"
    ):
        validate_case(data)


def test_product_relation_illegal_enum_rejected() -> None:
    data = _base_case()
    data["references"][0]["productRelation"] = "same"
    with pytest.raises(
        SkillPreviewError, match=r"references\[0\]\.productRelation 非法取值"
    ):
        validate_case(data)


def test_ai_status_illegal_enum_rejected() -> None:
    data = _base_case()
    data["references"][0]["aiStatus"] = "maybe"
    with pytest.raises(SkillPreviewError, match=r"references\[0\]\.aiStatus 非法取值"):
        validate_case(data)


# ---------- CLI 非零退出 ----------


def test_cli_nonzero_on_bad_case(tmp_path: Path) -> None:
    from backend.skill_preview.__main__ import main

    data = _base_case()
    data["referenceUsage"][0]["refImageId"] = "missing"
    code = main(["--family", "main", "--case", str(_write_case(tmp_path, data))])
    assert code == 1


def test_cli_zero_on_good_case() -> None:
    from backend.skill_preview.__main__ import main

    code = main(["--family", "main", "--case", str(CASE_PATH)])
    assert code == 0


# ---------- 真实图片进入请求 ----------


def _real_case(urls: list[str]) -> dict:
    data = _base_case()
    for i, url in enumerate(urls):
        data["references"][i]["url"] = url
    data["referenceUsage"] = data["referenceUsage"][: len(urls)]
    data["references"] = data["references"][: len(urls)]
    return data


def test_real_images_enter_content_array(tmp_path: Path, monkeypatch) -> None:
    from backend import db

    upload = tmp_path / "uploads"
    upload.mkdir()
    (upload / "a.png").write_bytes(b"img-a")
    (upload / "b.png").write_bytes(b"img-b")
    (upload / "c.png").write_bytes(b"img-c")
    monkeypatch.setattr(db, "UPLOAD_DIR", upload)

    result = assemble_request(
        "main",
        str(
            _write_case(
                tmp_path,
                _real_case(["/uploads/a.png", "/uploads/b.png", "/uploads/c.png"]),
            )
        ),
    )
    content = result["model_request"]["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    imgs = _image_blocks(result)
    assert len(imgs) == 3
    assert imgs[0]["image_url"]["url"].startswith("data:image/png;base64,")
    # 物理顺序 = referenceUsage = A/B/C
    assert result["ref_order"][0]["refImageId"] == "ref-A"
    assert result["assembly_status"]["images_resolved"] is True
    assert result["assembly_status"]["images_missing"] == []


def test_missing_upload_file_raises_with_ref(tmp_path: Path, monkeypatch) -> None:
    from backend import db

    upload = tmp_path / "uploads"
    upload.mkdir()
    (upload / "a.png").write_bytes(b"img-a")
    monkeypatch.setattr(db, "UPLOAD_DIR", upload)

    with pytest.raises(SkillPreviewError, match="ref-B") as exc:
        assemble_request(
            "main",
            str(
                _write_case(
                    tmp_path,
                    _real_case(["/uploads/a.png", "/uploads/b-missing.png"]),
                )
            ),
        )
    assert "b-missing.png" in str(exc.value)


# ---------- 与方案接口约束一致 ----------


def test_plan_roles_enums_match_schemas() -> None:
    from backend.schemas import AI_STATUSES, PLAN_ROLES, PRODUCT_RELATIONS
    from backend.skill_preview.assemble import AI_LABELS, RELATION_LABELS, ROLE_LABELS

    assert set(ROLE_LABELS) == set(PLAN_ROLES)
    assert set(RELATION_LABELS) == set(PRODUCT_RELATIONS)
    assert set(AI_LABELS) == set(AI_STATUSES)


def test_load_case_reads_shipped_fixture() -> None:
    case = load_case(CASE_PATH)
    assert case["family"] == "main"
    assert len(case["referenceUsage"]) == 3

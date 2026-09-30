"""组装模型请求：规则 + case 输入 → 可预览的 request payload。"""

from __future__ import annotations

from typing import Any

from .loader import SkillPreviewError, load_case, load_rules

ROLE_LABELS = {
    "primary": "主体依据",
    "detail": "细节补充",
    "usage": "安装与使用",
    "composition": "构图参考",
    "style": "视觉风格",
}

RELATION_LABELS = {
    "same_product": "同款同规格",
    "other_product": "其他商品",
    "no_product": "不含商品",
    "unknown": "不确定",
}

AI_LABELS = {
    "yes": "经过 AI 处理",
    "no": "未经 AI 处理",
    "unknown": "不确定",
}


def _ref_label(index: int) -> str:
    return chr(ord("A") + index)


def _ref_map(case: dict[str, Any]) -> list[dict[str, Any]]:
    """按 referenceUsage 顺序建立 A/B/C ↔ refImageId 对照。"""
    refs_by_id: dict[str, dict[str, Any]] = {}
    for r in case.get("references", []):
        rid = r.get("id")
        if not rid:
            raise SkillPreviewError("references 条目缺少 id")
        refs_by_id[str(rid)] = r
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(case["referenceUsage"]):
        ref_id = item.get("refImageId") or ""
        ref = refs_by_id.get(ref_id)
        if ref is None:
            raise SkillPreviewError(
                f"referenceUsage 引用了不存在的 refImageId: {ref_id!r}"
            )
        rows.append(
            {
                "label": _ref_label(idx),
                "refImageId": ref_id,
                "roles": item.get("roles") or [],
                "useFor": item.get("useFor") or "",
                "ignore": item.get("ignore") or "",
                "productRelation": ref.get("productRelation", "unknown"),
                "aiStatus": ref.get("aiStatus", "unknown"),
                "desc": ref.get("desc") or "",
            }
        )
    return rows


def assemble_request(family: str, case_path: str) -> dict[str, Any]:
    """加载规则与 case，组装模型请求与预览元数据。"""
    rules = load_rules(family)
    case = load_case(case_path)

    if case.get("family") and case["family"] != family:
        raise SkillPreviewError(
            f"case.family={case['family']!r} 与 --family {family!r} 不一致"
        )

    product = case["product"]
    plan = case["plan"]
    ref_rows = _ref_map(case)

    system_parts = [body for _, body in rules["common"]]
    system_parts.append(rules["family_doc"][1])
    system_prompt = "\n\n---\n\n".join(system_parts)

    usage_lines = []
    for row in ref_rows:
        roles = (
            "、".join(ROLE_LABELS.get(str(r), str(r)) for r in row["roles"])
            or "（无角色）"
        )
        line = (
            f"{row['label']}（{row['refImageId']}）: {roles}"
            f"；使用「{row['useFor'] or '—'}」"
            f"；忽略「{row['ignore'] or '—'}」"
            f"；{RELATION_LABELS.get(row['productRelation'], row['productRelation'])}"
            f" / {AI_LABELS.get(row['aiStatus'], row['aiStatus'])}"
        )
        usage_lines.append(line)

    user_prompt = (
        f"## 商品资料\n"
        f"- 名称：{product.get('name', '')}\n"
        f"- 目标市场：{product.get('market', '')}\n"
        f"- 事实：{product.get('facts', '')}\n\n"
        f"## 方案\n"
        f"- 名称：{plan.get('name', '')}\n"
        f"- 用途：{plan.get('imageUsage', '')}\n"
        f"- 用户制图要求（原文保留）：{plan.get('drawingRequest', '')}\n\n"
        f"## 参考图与使用范围（顺序=使用顺序）\n"
        + "\n".join(f"- {line}" for line in usage_lines)
        + "\n\n请输出：设计说明、参考图使用安排、生图提示词、待确认问题。"
    )

    model_request = {
        "model": "TBD-next-round",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    return {
        "family": family,
        "loaded_rules": rules["loaded_paths"],
        "ref_order": [
            {"label": r["label"], "refImageId": r["refImageId"]} for r in ref_rows
        ],
        "ref_detail": ref_rows,
        "model_request": model_request,
        "field_mapping": {
            "product.name/market/facts": "user_prompt §商品资料",
            "plan.name/imageUsage": "user_prompt §方案",
            "plan.drawingRequest": "user_prompt §方案（原文保留）",
            "referenceUsage[]": "user_prompt §参考图与使用范围",
            "参考图身份 refImageId": "ref_order / ref_detail，顺序一致",
            "designNotes": "建议输出，本轮不入库",
            "usageSummary / prompt": "已有 image_plans 列",
            "openQuestions": "建议输出，本轮不入库",
        },
        "gaps": [
            "designNotes 尚未写入 image_plans",
            "openQuestions 尚未写入 image_plans",
        ],
    }

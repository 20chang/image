"""组装模型请求：规则 + case 输入 → 可预览的 request payload。"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .loader import REPO_ROOT, SkillPreviewError, load_case, load_rules

try:
    from backend import db as _db
except ImportError:  # pragma: no cover - CLI without db side effects
    _db = None

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

_UPLOAD_PREFIX = "/uploads/"
_FIXTURE_PREFIXES = ("/static/fixtures/", "fixture:")


def _ref_label(index: int) -> str:
    return chr(ord("A") + index)


def _is_placeholder(url: str) -> bool:
    return not url or url.startswith(_FIXTURE_PREFIXES)


def _image_status(url: str) -> str:
    """测试占位与真实图片路径的展示状态。"""
    if not url:
        return "未提供地址"
    if _is_placeholder(url):
        return "测试占位（未提供真实图片）"
    return "已提供地址（图片内容待解析）"


def _resolve_local_path(url: str) -> Path | None:
    """把 /uploads/… 解析为本地文件；其余地址不解析。"""
    if _is_placeholder(url):
        return None
    if url.startswith(_UPLOAD_PREFIX):
        upload_dir = (
            Path(_db.UPLOAD_DIR)
            if _db is not None
            else REPO_ROOT / "backend" / "data" / "uploads"
        )
        return upload_dir / url[len(_UPLOAD_PREFIX) :]
    if url.startswith("file://"):
        return Path(url[7:])
    return None


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower() or ".png"
    mime = mimetypes.types_map.get(suffix, "image/png")
    data = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _image_part(row: dict[str, Any]) -> dict[str, Any] | None:
    """读取真实图片为 image_url 块；占位或外部地址返回 None。"""
    url = row["url"] or ""
    path = _resolve_local_path(url)
    if path is None:
        return None
    if not path.is_file():
        raise SkillPreviewError(
            f"参考图文件不存在: refImageId={row['refImageId']!r} "
            f"url={url!r} 解析路径={path}"
        )
    return {
        "type": "image_url",
        "image_url": {"url": _image_data_url(path)},
    }


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
        url = ref.get("url") or ""
        rows.append(
            {
                "label": _ref_label(idx),
                "refImageId": ref_id,
                "url": url,
                "imageStatus": _image_status(url),
                "roles": item.get("roles") or [],
                "useFor": item.get("useFor") or "",
                "ignore": item.get("ignore") or "",
                "productRelation": ref.get("productRelation", "unknown"),
                "aiStatus": ref.get("aiStatus", "unknown"),
                "desc": ref.get("desc") or "",
            }
        )
    return rows


def _usage_line(row: dict[str, Any]) -> str:
    roles = (
        "、".join(ROLE_LABELS.get(str(r), str(r)) for r in row["roles"]) or "（无角色）"
    )
    desc = row["desc"] or "—"
    return (
        f"{row['label']}（{row['refImageId']}）"
        f"；角色：{roles}"
        f"；使用「{row['useFor'] or '—'}」"
        f"；忽略「{row['ignore'] or '—'}」"
        f"；备注：{desc}"
        f"；{RELATION_LABELS.get(row['productRelation'], row['productRelation'])}"
        f" / {AI_LABELS.get(row['aiStatus'], row['aiStatus'])}"
    )


def _image_line(row: dict[str, Any]) -> str:
    roles = (
        "、".join(ROLE_LABELS.get(str(r), str(r)) for r in row["roles"]) or "（无角色）"
    )
    return (
        f"{row['label']}（{row['refImageId']}）"
        f"；来源：{row['url'] or '—'}"
        f"；状态：{row['imageStatus']}"
        f"；角色：{roles}"
        f"；使用「{row['useFor'] or '—'}」"
        f"；忽略「{row['ignore'] or '—'}」"
    )


def assemble_from_case(family: str, case: dict[str, Any]) -> dict[str, Any]:
    """加载规则并按 case dict 组装模型请求（夹具与库数据同构入口）。"""
    rules = load_rules(family)

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

    image_parts: list[dict[str, Any]] = []
    images_missing: list[str] = []
    local_total = 0
    for row in ref_rows:
        path = _resolve_local_path(row["url"] or "")
        if path is not None:
            local_total += 1
        try:
            part = _image_part(row)
        except SkillPreviewError as exc:
            images_missing.append(row["refImageId"])
            raise SkillPreviewError(str(exc)) from exc
        if part is not None:
            image_parts.append(part)
            row["imageStatus"] = "已解析图片（像素已入请求）"

    images_resolved = local_total > 0 and len(image_parts) == local_total

    # 文字说明与图片输入都按 referenceUsage 顺序（=使用顺序）
    usage_lines = [_usage_line(row) for row in ref_rows]
    image_lines = [_image_line(row) for row in ref_rows]

    user_prompt = (
        f"## 商品资料\n"
        f"- 名称：{product.get('name', '')}\n"
        f"- 目标市场：{product.get('market', '')}\n"
        f"- 事实：{product.get('facts', '')}\n\n"
        f"## 方案\n"
        f"- 名称：{plan.get('name', '')}\n"
        f"- 用途：{plan.get('imageUsage', '')}\n"
        f"- 用户制图要求（原文保留）：{plan.get('drawingRequest', '')}\n\n"
        f"## 参考图文字说明（顺序=使用顺序）\n"
        + "\n".join(f"- {line}" for line in usage_lines)
        + "\n\n## 参考图图片输入（顺序=使用顺序，与上表一一对应）\n"
        + "\n".join(f"- {line}" for line in image_lines)
        + "\n\n## 组装状态\n"
        + (
            "- 已组装：规则文本、商品资料、方案字段、参考图文字说明；图片像素已随请求传入。\n"
            if images_resolved
            else "- 已组装：规则文本、商品资料、方案字段、参考图文字说明与图片输入清单。\n"
            "- 待适配：图片像素内容尚未解析（当前无模型提供者）；上表「来源」是路径文本，"
            "不代表模型已收到图片。\n"
        )
        + "- 未执行：模型调用、图片生成。\n\n"
        "请输出：设计说明、参考图使用安排、生图提示词、待确认问题。"
    )

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    # 图片物理顺序严格等于 referenceUsage 顺序（A/B/C）
    user_content.extend(image_parts)

    model_request = {
        "model": "TBD-next-round",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    image_inputs = [
        {
            "label": r["label"],
            "refImageId": r["refImageId"],
            "url": r["url"],
            "status": r["imageStatus"],
            "roles": r["roles"],
            "useFor": r["useFor"],
            "ignore": r["ignore"],
        }
        for r in ref_rows
    ]

    return {
        "family": family,
        "loaded_rules": rules["loaded_paths"],
        "ref_order": [
            {"label": r["label"], "refImageId": r["refImageId"]} for r in ref_rows
        ],
        "ref_detail": ref_rows,
        "image_inputs": image_inputs,
        "model_request": model_request,
        "assembly_status": {
            "rules_loaded": True,
            "request_assembled": True,
            "images_resolved": images_resolved,
            "images_missing": images_missing,
            "image_parts": len(image_parts),
            "model_called": False,
            "image_generated": False,
            "note": (
                "全部本地参考图像素已进入 messages。"
                if images_resolved
                else "图片路径为文本清单或占位，像素内容待模型提供者适配后解析。"
            ),
        },
        "field_mapping": {
            "product.name/market/facts": "user_prompt §商品资料",
            "plan.name/imageUsage": "user_prompt §方案",
            "plan.drawingRequest": "user_prompt §方案（原文保留）",
            "referenceUsage[]": "user_prompt §参考图文字说明 + §参考图图片输入",
            "ReferenceOut.desc": "user_prompt §参考图文字说明（备注）",
            "ReferenceOut.url": "user_prompt §参考图图片输入（来源）+ messages 图片段",
            "参考图身份 refImageId": "ref_order / image_inputs，顺序一致",
            "designNotes": "建议输出，本轮不入库",
            "usageSummary / prompt": "已有 image_plans 列",
            "openQuestions": "建议输出，本轮不入库",
        },
        "gaps": [
            "designNotes 尚未写入 image_plans",
            "openQuestions 尚未写入 image_plans",
            "图片像素内容尚未解析（无模型提供者）",
        ]
        if not images_resolved
        else [
            "designNotes 尚未写入 image_plans",
            "openQuestions 尚未写入 image_plans",
        ],
    }


def assemble_request(family: str, case_path: str) -> dict[str, Any]:
    """加载规则与 case，组装模型请求与预览元数据。"""
    case = load_case(case_path)
    return assemble_from_case(family, case)

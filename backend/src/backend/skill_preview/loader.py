"""加载 skills/ 规则与 case 输入，并做与方案接口一致的校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.schemas import PLAN_ROLES

# skills/ 在仓库根目录：backend/src/backend/skill_preview/loader.py → 上溯 4 层
REPO_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = REPO_ROOT / "skills"

COMMON_FILES = ("00-overview.md", "10-io-contract.md")

FAMILY_FILES = {
    "main": "main.md",
    "wear": "wear.md",
    "handheld": "handheld.md",
    "scene": "scene.md",
    "texture": "texture.md",
    "compare": "compare.md",
}

REQUIRED_CASE_KEYS = ("family", "product", "plan", "references", "referenceUsage")


class SkillPreviewError(Exception):
    """规则或 case 加载/校验失败。消息含出错位置。"""


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise SkillPreviewError(f"文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def load_rules(family: str) -> dict[str, Any]:
    """读取通用规则 + 指定族规则，返回路径与正文。"""
    if family not in FAMILY_FILES:
        raise SkillPreviewError(
            f"未知族: {family!r}，可选: {', '.join(sorted(FAMILY_FILES))}"
        )

    common_paths = [SKILLS_ROOT / "common" / name for name in COMMON_FILES]
    family_path = SKILLS_ROOT / "families" / FAMILY_FILES[family]

    common_docs = [(str(p), _read_text(p)) for p in common_paths]
    family_doc = (str(family_path), _read_text(family_path))

    return {
        "family": family,
        "common": common_docs,
        "family_doc": family_doc,
        "loaded_paths": [p for p, _ in common_docs] + [str(family_path)],
    }


def _require_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SkillPreviewError(f"{where} 必须是对象，实际是 {type(value).__name__}")
    return value


def _require_str(value: Any, where: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise SkillPreviewError(f"{where} 必须是字符串，实际是 {type(value).__name__}")
    if not allow_empty and not value.strip():
        raise SkillPreviewError(f"{where} 不能为空")
    return value


def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise SkillPreviewError(f"{where} 必须是数组，实际是 {type(value).__name__}")
    return value


def validate_case(data: dict[str, Any], *, source: str = "case") -> dict[str, Any]:
    """校验 case 结构与业务约束；错误消息带字段位置。"""
    for key in REQUIRED_CASE_KEYS:
        if key not in data:
            raise SkillPreviewError(f"{source} 缺少字段 {key!r}")

    _require_str(data.get("family"), f"{source}.family", allow_empty=False)

    product = _require_dict(data["product"], f"{source}.product")
    _require_str(product.get("name", ""), f"{source}.product.name")

    plan = _require_dict(data["plan"], f"{source}.plan")
    _require_str(plan.get("name", ""), f"{source}.plan.name", allow_empty=False)
    _require_str(plan.get("drawingRequest", ""), f"{source}.plan.drawingRequest")

    refs_raw = _require_list(data["references"], f"{source}.references")
    refs_by_id: dict[str, dict[str, Any]] = {}
    for i, ref in enumerate(refs_raw):
        where = f"{source}.references[{i}]"
        ref = _require_dict(ref, where)
        rid = ref.get("id")
        if not rid or not isinstance(rid, str):
            raise SkillPreviewError(f"{where}.id 必须是非空字符串")
        if rid in refs_by_id:
            raise SkillPreviewError(f"{where}.id 重复: {rid!r}")
        _require_str(ref.get("url", ""), f"{where}.url")
        _require_str(ref.get("desc", ""), f"{where}.desc")
        refs_by_id[rid] = ref

    usage_raw = _require_list(data["referenceUsage"], f"{source}.referenceUsage")
    seen: set[str] = set()
    primary_count = 0
    for i, item in enumerate(usage_raw):
        where = f"{source}.referenceUsage[{i}]"
        item = _require_dict(item, where)
        ref_id = item.get("refImageId")
        if not ref_id or not isinstance(ref_id, str):
            raise SkillPreviewError(f"{where}.refImageId 必须是非空字符串")
        if ref_id in seen:
            raise SkillPreviewError(f"{where}.refImageId 重复引用: {ref_id!r}")
        seen.add(ref_id)
        if ref_id not in refs_by_id:
            raise SkillPreviewError(
                f"{where}.refImageId 不存在于 references: {ref_id!r}"
            )
        roles = _require_list(item.get("roles", []), f"{where}.roles")
        for j, role in enumerate(roles):
            if role not in PLAN_ROLES:
                raise SkillPreviewError(
                    f"{where}.roles[{j}] 非法角色: {role!r}，可选: {sorted(PLAN_ROLES)}"
                )
        if "primary" in roles:
            primary_count += 1
            if primary_count > 1:
                raise SkillPreviewError(f"{where}.roles 至多一个 primary 参考图")
        _require_str(item.get("useFor", ""), f"{where}.useFor")
        _require_str(item.get("ignore", ""), f"{where}.ignore")

    return data


def load_case(case_path: str | Path) -> dict[str, Any]:
    """读取并校验 case JSON（测试样例输入）。"""
    path = Path(case_path)
    if not path.is_file():
        raise SkillPreviewError(f"case 文件不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillPreviewError(f"case JSON 解析失败: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SkillPreviewError(f"case 顶层必须是对象: {path}")

    return validate_case(data, source=f"case({path.name})")

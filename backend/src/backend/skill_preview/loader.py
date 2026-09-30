"""加载 skills/ 规则与 case 输入。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


class SkillPreviewError(Exception):
    """规则或 case 加载失败。"""


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


def load_case(case_path: str | Path) -> dict[str, Any]:
    """读取 case JSON（测试样例输入）。"""
    path = Path(case_path)
    if not path.is_file():
        raise SkillPreviewError(f"case 文件不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillPreviewError(f"case JSON 解析失败: {path}: {exc}") from exc

    for key in ("family", "product", "plan", "references", "referenceUsage"):
        if key not in data:
            raise SkillPreviewError(f"case 缺少字段 {key!r}: {path}")

    if not isinstance(data["referenceUsage"], list):
        raise SkillPreviewError(f"case.referenceUsage 必须是数组: {path}")

    return data

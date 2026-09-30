"""CLI 入口：uv run python -m backend.skill_preview --family main --case …"""

from __future__ import annotations

import argparse
import json
import sys

from .assemble import assemble_request
from .loader import SkillPreviewError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="backend.skill_preview",
        description="组装图片方案 Skill 模型请求并预览（不调用模型）",
    )
    parser.add_argument(
        "--family",
        required=True,
        choices=["main", "wear", "handheld", "scene", "texture", "compare"],
        help="图片族",
    )
    parser.add_argument(
        "--case",
        required=True,
        help="case JSON 路径，如 ../skills/cases/car-light-main.case.json",
    )
    parser.add_argument(
        "--plan-id",
        default=None,
        help="（可选）从本地库读取真实方案；本轮默认走 case 文件",
    )
    args = parser.parse_args(argv)

    if args.plan_id:
        print(
            "[warn] --plan-id 本轮未接库，仍使用 --case 文件输入。",
            file=sys.stderr,
        )

    try:
        result = assemble_request(args.family, args.case)
    except SkillPreviewError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("1. 加载的规则文件")
    print("=" * 60)
    for path in result["loaded_rules"]:
        print(f"  - {path}")

    print()
    print("=" * 60)
    print("2. 参考图顺序对照（顺序=使用顺序）")
    print("=" * 60)
    for row in result["ref_order"]:
        print(f"  {row['label']}  ↔  {row['refImageId']}")

    print()
    print("=" * 60)
    print("3. 组装后的模型请求 (messages)")
    print("=" * 60)
    print(json.dumps(result["model_request"], ensure_ascii=False, indent=2))

    print()
    print("=" * 60)
    print("4. 与方案字段的映射说明")
    print("=" * 60)
    for src, dst in result["field_mapping"].items():
        print(f"  {src}  →  {dst}")
    for gap in result["gaps"]:
        print(f"  [gap] {gap}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

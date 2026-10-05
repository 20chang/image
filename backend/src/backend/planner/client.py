"""规划模型薄客户端：messages（含图片）→ 文本。不接生图。"""

from __future__ import annotations

import json
import os
from typing import Any


class PlannerError(Exception):
    """调用或解析规划模型失败。保留原始输出便于落 run。"""

    def __init__(self, message: str, *, raw_output: str | None = None) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class PlannerConfigError(PlannerError):
    """缺少必要配置。"""


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise PlannerConfigError(f"缺少环境变量 {name}")
    return value


def load_config() -> dict[str, str]:
    return {
        "model": _require_env("PLANNER_MODEL"),
        "base_url": _require_env("PLANNER_BASE_URL").rstrip("/"),
        "api_key": _require_env("PLANNER_API_KEY"),
    }


def parse_plan_output(raw: str) -> dict[str, Any]:
    """解析规划模型固定 JSON 输出；失败抛 PlannerError 并带 raw。"""
    text = (raw or "").strip()
    if not text:
        raise PlannerError("规划模型返回空输出", raw_output=raw)
    # 允许模型包一层 ```json
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerError(f"规划模型输出不是合法 JSON: {exc}", raw_output=raw) from exc
    if not isinstance(data, dict):
        raise PlannerError("规划模型输出必须是 JSON 对象", raw_output=raw)

    def _str(key: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) else ""

    def _str_list(key: str) -> list[str]:
        value = data.get(key)
        if not isinstance(value, list):
            return []
        return [str(x) for x in value]

    prompt = _str("prompt")
    if not prompt.strip():
        raise PlannerError("规划模型输出缺少 prompt", raw_output=raw)

    return {
        "designNotes": _str("designNotes"),
        "prompt": prompt,
        "openQuestions": _str_list("openQuestions"),
        "refUsageNotes": _str("refUsageNotes"),
    }


def run_planner(
    messages: list[dict[str, Any]],
    *,
    config: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> str:
    """调用 OpenAI 兼容 chat/completions，返回 assistant 文本。"""
    cfg = config or load_config()
    import httpx

    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.2,
    }
    try:
        resp = httpx.post(
            f"{cfg['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise PlannerError(f"规划模型请求失败: {exc}") from exc

    if resp.status_code >= 400:
        raise PlannerError(
            f"规划模型 HTTP {resp.status_code}: {resp.text[:500]}",
            raw_output=resp.text,
        )
    try:
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise PlannerError(
            f"规划模型响应结构异常: {exc}", raw_output=resp.text
        ) from exc
    if not isinstance(content, str):
        raise PlannerError("规划模型 content 必须是字符串", raw_output=resp.text)
    return content

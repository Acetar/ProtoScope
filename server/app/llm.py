"""
大模型编排：只让模型产出 AnimationProps JSON，绝不让它写组件代码。

默认对接 DeepSeek（OpenAI 兼容）：base_url = https://api.deepseek.com，
model = deepseek-chat。key 由用户在设置里自己填（BYOK），
服务端不落任何全局密钥；没有可用 key 时回退到规则库。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是网络协议教学动画的编排器。把用户需求转成一份 JSON 剧本，供 Remotion 渲染成两方通信的时序动画。

硬性约束：
1. 只能用两个通信主体（actors 恰好 2 个），x 固定 300 与 1000，y 固定 250。
2. icon 只能取 laptop / server / cloud / router。
3. fps=30, width=1920, height=1080, templateId="ProtocolFlow"。
4. scenes 3~5 个，每个场景 durationInFrames 在 150~180 之间；场景首尾相接，startFrame 依次累加。
5. 每个场景最多 1 条 packet-fly（报文），delay=18，durationInFrames=60；第 4 个场景允许 2 条。
6. packet-fly 的 from/to 必须是 actors 的 id；fields 只放真实存在的字段（seq/ack/flags/len）。
7. captions 每个场景一条，落在该场景内，文本不超过 26 个汉字。
8. narration 用中文，讲清“为什么”，不要只描述现象。
9. 只输出 JSON 对象，不要 markdown 代码块，不要解释。

JSON 结构：
{
  "knowledgePoint": "tls.handshake",
  "templateId": "ProtocolFlow",
  "title": "标题",
  "subtitle": "一句副标题",
  "fps": 30, "width": 1920, "height": 1080,
  "totalFrames": 480,
  "actors": [{"id":"client","label":"客户端","icon":"laptop","x":300,"y":250,"initialState":"READY"},
             {"id":"server","label":"服务端","icon":"server","x":1000,"y":250,"initialState":"LISTEN"}],
  "scenes": [{
    "id": "scene-1", "title": "场景标题", "startFrame": 0, "durationInFrames": 160,
    "narration": "讲解词",
    "actions": [{"type":"packet-fly","from":"client","to":"server","label":"SYN","delay":18,
                 "durationInFrames":60,"fields":{"seq":"100","flags":"SYN"},"color":"#ffb454"},
                {"type":"state-change","actor":"client","from":"READY","to":"WAIT","delay":18}]
  }],
  "captions": [{"startFrame": 24, "endFrame": 140, "text": "字幕"}],
  "audioSrc": null
}"""


class LLMUnavailable(RuntimeError):
    """没有可用配置，或调用失败/超时。"""


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        # 用户可能填 https://api.deepseek.com，也可能填 .../v1
        return f"{base}/chat/completions"


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def plan(
    cfg: LLMConfig,
    prompt: str,
    duration_hint: str,
    feedback: str | None = None,
) -> dict:
    """调用一次模型；feedback 用于把校验错误回灌给模型重试。"""
    user = f"用户需求：{prompt}\n目标时长：约 {duration_hint}。请直接输出 JSON。"
    if feedback:
        user += f"\n\n上一次输出未通过校验，错误如下，请修正后重新输出：\n{feedback}"

    payload = {
        "model": cfg.model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                cfg.endpoint,
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                json=payload,
            )
            if resp.status_code == 401:
                raise LLMUnavailable("API key 无效或已过期，请到设置里重新填写")
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise LLMUnavailable(f"模型返回 {exc.response.status_code}：{exc.response.text[:200]}") from exc
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"模型调用失败：{exc}") from exc
    except (KeyError, IndexError) as exc:
        raise LLMUnavailable("模型返回结构不符合 OpenAI 兼容格式") from exc

    try:
        data = _extract_json(content)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"模型返回的不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("模型返回的 JSON 顶层必须是对象")
    return data

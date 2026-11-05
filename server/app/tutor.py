"""AI 教师（B1）：把「当前知识点的结构化上下文」交给模型，让它讲课或答疑。

设计原则和动画生成那条线一致——不让模型凭空编：
1. 上下文是规则层组织的（知识点定义 + 关键报文 + 字段），几百 token，不是整份抓包；
2. 回答要求分点、给例子、指出常见误解，控制在口播长度；
3. 模型不可用时回退到规则模板（降级链的最后一环），保证断网也能演示。

与 llm.py 的分工：llm.py 产出 AnimationProps JSON，本模块产出自然语言。
两者共用 LLMConfig / LLMUnavailable，避免再写一份 HTTP 客户端。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import httpx

from . import llm

TEACHER_SYSTEM = """你是一位计算机网络课程的教师，正在给一名本科生做一对一讲解。

讲解风格：
1. 先说结论，再说原因，最后点出常见误解。不要写成百科词条。
2. 涉及报文时，必须用上下文里给出的真实字段值（seq、ack、flags、端口号），不要自己编数字。
3. 如果上下文里没有的信息，就说"这一点需要查证"，不要猜。
4. 中文回答，控制在 350 字以内，可以用简单的列表，不要用 markdown 标题。
5. 结尾给一个"你可以这样验证"的小建议（比如用 Wireshark 过滤什么、看哪个字段）。"""


@dataclass
class Context:
    """回答时允许引用的全部事实来源。"""

    knowledge_point: str = ""
    title: str = ""
    summary: str = ""
    actors: list[str] | None = None
    scenes: list[dict] | None = None

    def as_prompt(self) -> str:
        lines = ["【当前知识点】", f"{self.title}（{self.knowledge_point}）", self.summary]
        if self.actors:
            lines.append(f"通信双方：{' ↔ '.join(self.actors)}")
        if self.scenes:
            lines.append("")
            lines.append("【涉及的报文】")
            for i, s in enumerate(self.scenes, 1):
                head = f"{i}. {s.get('title', '')}"
                nar = s.get("narration")
                if nar:
                    head += f" —— {nar}"
                lines.append(head)
                for f in s.get("fields", []):
                    lines.append(f"   - {f}")
        return "\n".join(lines)


def scenes_from_props(props: dict) -> list[dict]:
    """把 AnimationProps 折成"讲解够用"的场景摘要：标题 + 旁白 + 报文字段。"""
    out: list[dict] = []
    for s in props.get("scenes", []):
        fields: list[str] = []
        for act in s.get("actions", []):
            if act.get("type") == "packet-fly":
                kv = ", ".join(f"{k}={v}" for k, v in (act.get("fields") or {}).items())
                fields.append(f"{act.get('label', '报文')}：{kv}" if kv else str(act.get("label", "报文")))
        out.append({"title": s.get("title", ""), "narration": s.get("narration", ""), "fields": fields})
    return out


def build_context(topic: dict | None, scenes: list[dict] | None = None) -> Context:
    if not topic:
        return Context(scenes=scenes)
    return Context(
        knowledge_point=topic.get("id", ""),
        title=topic.get("title", ""),
        summary=topic.get("summary", ""),
        actors=topic.get("actors") or [],
        scenes=scenes,
    )


def offline_answer(question: str, ctx: Context) -> str:
    """没有可用模型时的兜底：用规则拼一段仍然有用的回答。"""
    name = ctx.title or "这个知识点"
    head = f"（当前没有可用的模型 key，下面是基于知识库的要点）\n\n"
    body = f"你问的是「{question}」，我按{name}的固定剧本给你拆一下：\n"
    if ctx.scenes:
        for i, s in enumerate(ctx.scenes, 1):
            nar = s.get("narration") or s.get("title", "")
            body += f"{i}. {nar}\n"
    else:
        body += f"{ctx.summary}\n"
    body += "\n到「知识点动画」里点开这个剧本，逐帧看报文上的 seq / ack 变化，比读文字快。"
    body += "\n验证建议：在 Wireshark 里用 tcp.flags.syn == 1 过滤，只留 SYN 相关的包。"
    return head + body


def _stream_deepseek(cfg: llm.LLMConfig, messages: list[dict]) -> Iterator[str]:
    payload = {
        "model": cfg.model,
        "temperature": 0.4,
        "stream": True,
        "messages": messages,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                cfg.endpoint,
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                json=payload,
            ) as resp:
                if resp.status_code == 401:
                    raise llm.LLMUnavailable("API key 无效或已过期，请到设置里重新填写")
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        import json as _json

                        delta = _json.loads(data)["choices"][0]["delta"]
                    except (ValueError, KeyError, IndexError):
                        continue
                    piece = delta.get("content")
                    if piece:
                        yield piece
    except httpx.HTTPStatusError as exc:
        raise llm.LLMUnavailable(f"模型返回 {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise llm.LLMUnavailable(f"模型调用失败：{exc}") from exc


def answer(cfg: llm.LLMConfig | None, ctx: Context, question: str, history: list[dict]) -> Iterator[str]:
    """返回 SSE 用的文本片段流；无模型时直接吐兜底文案。"""
    if cfg is None:
        yield offline_answer(question, ctx)
        return

    messages = [{"role": "system", "content": TEACHER_SYSTEM + "\n\n" + ctx.as_prompt()}]
    for h in history[-6:]:
        role = h.get("role")
        if role in ("user", "assistant") and h.get("content"):
            messages.append({"role": role, "content": h["content"]})
    messages.append({"role": "user", "content": question})

    try:
        yield from _stream_deepseek(cfg, messages)
    except llm.LLMUnavailable as exc:
        yield offline_answer(question, ctx) + f"\n\n（模型调用失败：{exc}）"

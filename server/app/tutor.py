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

from . import catalog, llm

TEACHER_SYSTEM = """你是一位计算机网络课程的助教，正在和一名本科生一对一聊天。

说话方式：
1. 像人一样对话——他打招呼就打招呼，他闲聊就聊两句，别硬往知识点上拐。
2. 讲原理时先说结论，再说原因，最后点出容易误解的地方；可以用 "1. 2. 3." 或 "· " 分条，
   不要写 markdown 标题、不要画大表格。
3. 涉及报文时必须用上下文里给出的真实字段值（seq / ack / flags / 端口），不要自己编数字。
4. 上下文里没有的信息就说"这个我没把握"，不要猜。
5. 中文口语化，一般 200–350 字；只是寒暄就一两句，不必展开。
6. 用户说"画一个 / 生成动画 / 演示一下"时，回一句"好，我这就排一段"即可——
   动画由系统在这条对话里生成，你不要描述分镜。"""


# ---------- 意图识别（不依赖模型，降级时也要能"听懂人话"） ----------

_GREET = ("你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗", "在么", "早上好", "中午好", "晚上好")
_THANKS = ("谢谢", "多谢", "thanks", "thx", "受教")
_AGREE = ("明白了", "懂了", "知道了", "原来如此", "好的", "ok", "OK")
_CAPABILITY = (
    "你能做什么",
    "你会什么",
    "能干什么",
    "能做什么",
    "怎么用",
    "你是谁",
    "介绍一下自己",
    "自我介绍",
    "帮助",
    "help",
)
_ANIMATE = ("动画", "动效", "视频", "演示", "画一个", "画个", "画一段", "生成", "做个", "来一段", "播放", "出片")


def animation_intent(question: str) -> dict | None:
    """用户是否在要求"生成一段动画"；命中时返回可执行的动作描述。"""
    q = (question or "").strip()
    if not q or not any(k in q.lower() for k in _ANIMATE):
        return None
    return {"type": "animate", "topicId": catalog.match_text(q) or "", "prompt": q}


def _hit(text: str, keys: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(k.lower() in low for k in keys)


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


# ---------- 兜底回答：没有模型 key / 模型挂了时的人话 ----------


def _smalltalk(question: str) -> str | None:
    """寒暄、道谢、问"你能干什么"——这些话不该被硬套进知识点剧本。"""
    q = question.strip()
    if len(q) <= 16 and _hit(q, _GREET):
        return (
            "你好，我是这门课的助教。\n\n"
            "可以问我原理，比如「为什么三次握手不是两次，两次会怎样」；"
            "也可以直接说「画一个 DNS 递归解析的动画」，我在这条对话里给你排出来。\n\n"
            "想从哪儿开始？"
        )
    if len(q) <= 12 and _hit(q, _THANKS):
        return "不客气。还有哪块想细看的？报文里的字段怎么变，或者某一步为什么要这么设计，都可以问。"
    if len(q) <= 12 and _hit(q, _AGREE):
        return "那我们往下走。要不要我把它变成动画看一遍，或者挑其中某一步展开？"
    if _hit(q, _CAPABILITY):
        return (
            "我能做三件事：\n\n"
            "· 讲原理——三次握手、DNS 递归/迭代、DHCP、NAT 这些，我按「结论 → 原因 → 易错点」讲；\n"
            "· 看报文——你把某一段的 seq / ack / flags 贴过来，我逐字段解释它为什么是这个值；\n"
            "· 排动画——说一句「画一个 TCP 超时重传」，我直接在这条对话里生成一段可播放的动画。\n\n"
            "另外「知识点动画」页里有十二个我写好的剧本，也可以从那儿点开看。"
        )
    return None


def offline_answer(question: str, ctx: Context) -> str:
    """没有可用模型时的兜底：用规则拼一段仍然像人话的回答。"""
    q = (question or "").strip()

    small = _smalltalk(q)
    if small:
        return small

    if animation_intent(q):
        return (
            "好，我这就排一段——动画会直接出现在这条对话里，不用切页面。\n\n"
            "如果出来的画面和你想要的不一样，告诉我具体协议或者场景（比如“只看丢包重传那一段”），我换个剧本重排。"
        )

    # 用户没绑知识点，但问题里提到了某个剧本 —— 自动对上号，别要求他先去左边选
    topic = None
    if ctx.knowledge_point:
        topic = catalog.by_id(ctx.knowledge_point)
    if topic is None or not ctx.scenes:
        matched = catalog.match_text(q)
        if matched:
            topic = catalog.by_id(matched) or topic
            if topic and topic["id"] in catalog.BUILDERS:
                ctx = build_context(topic, scenes_from_props(catalog.BUILDERS[topic["id"]]()))

    if not ctx.scenes and not ctx.summary:
        return (
            "这个我一时答不上来，别让我瞎编。\n\n"
            "换个方式可能更快：\n"
            "· 报个协议名，比如「讲讲 ARP」；\n"
            "· 说「画一个 DHCP 获取地址的动画」，我直接出片；\n"
            "· 或者把 pcap 传到「抓包解析」里，我按你真实的报文解释。"
        )

    name = ctx.title or "这个知识点"
    out: list[str] = []
    if ctx.summary:
        out.append(f"先说结论：{ctx.summary}")
    if ctx.scenes:
        out.append(f"\n{name}的过程可以拆成 {len(ctx.scenes)} 步：")
        for i, s in enumerate(ctx.scenes, 1):
            nar = s.get("narration") or s.get("title", "")
            out.append(f"{i}. {nar}")

    fields = [f for s in (ctx.scenes or []) for f in s.get("fields", [])][:3]
    if fields:
        out.append("\n报文里最值得盯的字段：")
        out.extend(f"· {f}" for f in fields)

    if ctx.actors:
        out.append(f"\n看的时候注意发送方向：{' → '.join(ctx.actors)}，方向反了整段就讲不通了。")

    out.append("\n要不要我把它变成动画看一遍，或者挑其中某一步展开？")
    out.append("\n（离线模式：这段是按剧本拼的，配上模型 key 后可以自由追问。）")
    return "\n".join(out)


def _stream_deepseek(cfg: llm.LLMConfig, messages: list[dict]) -> Iterator[str]:
    payload = {
        "model": cfg.model,
        "temperature": 0.5,
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

    # 没有绑定知识点时也把"目录"告诉模型，让它能在用户提到协议时自己接上
    catalog_hint = "【可讲的知识点】" + "、".join(c["title"] for c in catalog.CATALOG)
    context = ctx.as_prompt() if (ctx.scenes or ctx.summary) else "（用户还没选知识点，按他问的来）"
    messages = [{"role": "system", "content": "\n\n".join([TEACHER_SYSTEM, context, catalog_hint])}]
    for h in history[-6:]:
        role = h.get("role")
        if role in ("user", "assistant") and h.get("content"):
            messages.append({"role": role, "content": h["content"]})
    messages.append({"role": "user", "content": question})

    try:
        yield from _stream_deepseek(cfg, messages)
    except llm.LLMUnavailable as exc:
        yield offline_answer(question, ctx) + f"\n\n（模型调用失败：{exc}）"

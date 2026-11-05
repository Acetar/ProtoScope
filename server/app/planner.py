"""
生成编排：需求 → AnimationProps。

优先级：目录命中（规则库，离线可用、质量稳定）→ 自由文本别名匹配 → 大模型。
两条路径的最后一步都一样：pydantic 校验 + 时长重排，所以输出永远满足同一份契约。
"""
from __future__ import annotations

import time
import uuid

from pydantic import ValidationError

from . import catalog, llm
from .builders import scale
from .models import AnimationProps, GenerateRequest, GenerateResponse, GenerateMeta

MIN_FRAMES = 8 * 30
MAX_FRAMES = 40 * 30


class NoMatchError(RuntimeError):
    """自由描述既没命中目录，也没法调用模型。"""

    def __init__(self, message: str, suggestions: list[str]):
        super().__init__(message)
        self.suggestions = suggestions


def _clean(props: dict) -> dict:
    """去掉空字段：Zod 的 optional 不接受 null，只接受缺省。"""
    for scene in props.get("scenes", []):
        for action in scene.get("actions", []):
            if isinstance(action.get("fields"), dict):
                action["fields"] = {
                    k: v for k, v in action["fields"].items() if v is not None and v != ""
                }
    props.setdefault("audioSrc", None)
    return props


def _dump(model: AnimationProps) -> dict:
    """序列化时再清一次：pydantic 会把未填的可选字段还原成 null。"""
    data = model.model_dump(by_alias=True)
    for scene in data.get("scenes", []):
        for action in scene.get("actions", []):
            if isinstance(action.get("fields"), dict):
                action["fields"] = {
                    k: v for k, v in action["fields"].items() if v is not None
                }
    data["audioSrc"] = model.audioSrc
    return data


def to_payload(resp: GenerateResponse) -> dict:
    """对外 JSON：fields 里的 null 必须省掉（Zod 的 optional 不接受 null）。"""
    return {"props": _dump(resp.props), "meta": resp.meta.model_dump()}


def _retime(props: dict, duration_sec: int) -> dict:
    target = max(MIN_FRAMES, min(MAX_FRAMES, round(duration_sec * 30)))
    factor = target / props["totalFrames"]
    return scale(props, factor)


def generate(req: GenerateRequest, cfg: llm.LLMConfig | None = None) -> GenerateResponse:
    started = time.perf_counter()
    notes: list[str] = []
    source = "catalog"

    kp_id: str | None = None
    if req.topic:
        kp_id = req.topic if req.topic in catalog.BUILDERS else None
        if kp_id is None:
            raise NoMatchError(
                f"目录里没有 {req.topic!r}",
                [c["id"] for c in catalog.CATALOG],
            )
    elif req.prompt:
        kp_id = catalog.match_text(req.prompt)

    if kp_id:
        props = catalog.BUILDERS[kp_id]()
        if req.prompt:
            notes.append(f"自由描述命中规则库：{kp_id}")
    else:
        source = "llm"
        compiled = _llm_with_retry(req.prompt or "", req.durationSec, cfg)
        props = compiled["props"]
        notes.extend(compiled["notes"])
        kp_id = props.get("knowledgePoint") or "custom"

    props = _retime(props, req.durationSec)
    props = _clean(props)

    try:
        model = AnimationProps(**props)
    except ValidationError as exc:
        raise NoMatchError(
            "生成结果没通过结构校验：" + _brief(exc), [c["id"] for c in catalog.CATALOG]
        ) from exc

    elapsed = int((time.perf_counter() - started) * 1000)
    return GenerateResponse(
        props=model,
        meta=GenerateMeta(
            source=source,
            knowledgePoint=kp_id or "custom",
            durationSec=round(model.totalFrames / model.fps, 2),
            totalFrames=model.totalFrames,
            elapsedMs=elapsed,
            notes=notes,
        ),
    )


def _llm_with_retry(prompt: str, duration_sec: int, cfg: llm.LLMConfig | None) -> dict:
    """模型输出校验失败时，把错误回灌一次；仍失败则抛给上层。"""
    notes: list[str] = []
    feedback: str | None = None

    if cfg is None:
        raise NoMatchError(
            "还没有配置大模型（在设置里填 DeepSeek API Key 即可），"
            "目前只能从左侧目录里选知识点。",
            [c["id"] for c in catalog.CATALOG],
        )

    for attempt in range(2):
        try:
            raw = llm.plan(cfg, prompt, f"{duration_sec} 秒", feedback)
        except llm.LLMUnavailable as exc:
            raise NoMatchError(
                f"{exc}。可以改用目录里的知识点，或在设置里换个 key 后重试。",
                [c["id"] for c in catalog.CATALOG],
            ) from exc

        raw = _normalize_llm(raw)
        try:
            AnimationProps(**_clean(dict(raw)))
        except ValidationError as exc:
            feedback = _brief(exc)
            notes.append(f"第 {attempt + 1} 次输出校验失败：{feedback}")
            continue

        notes.append("大模型编排，已通过结构校验")
        return {"props": raw, "notes": notes}

    raise NoMatchError(
        "大模型两次输出都没通过校验：" + (feedback or ""),
        [c["id"] for c in catalog.CATALOG],
    )


def _normalize_llm(raw: dict) -> dict:
    """模型容易漏字段/写错常量，这里做无争议的兜底修正。"""
    raw.setdefault("templateId", "ProtocolFlow")
    raw.setdefault("fps", 30)
    raw.setdefault("width", 1920)
    raw.setdefault("height", 1080)
    raw.setdefault("audioSrc", None)
    raw.setdefault("knowledgePoint", f"custom.{uuid.uuid4().hex[:6]}")

    actions_ok = {"packet-fly", "state-change", "pulse", "callout"}
    for scene in raw.get("scenes", []):
        scene.setdefault("id", f"scene-{uuid.uuid4().hex[:4]}")
        scene.setdefault("title", "场景")
        scene.setdefault("narration", "")
        scene.setdefault("actions", [])
        scene["actions"] = [a for a in scene["actions"] if a.get("type") in actions_ok]

    actors = raw.get("actors") or []
    if len(actors) < 2:
        raw["actors"] = [
            {"id": "client", "label": "客户端", "icon": "laptop", "x": 300, "y": 250,
             "initialState": "READY"},
            {"id": "server", "label": "服务端", "icon": "server", "x": 1000, "y": 250,
             "initialState": "LISTEN"},
        ]

    if "totalFrames" not in raw:
        total = 0
        for scene in raw.get("scenes", []):
            scene["startFrame"] = total
            total += int(scene.get("durationInFrames") or 160)
        raw["totalFrames"] = total or 480

    return raw


def _brief(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:4]:
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)

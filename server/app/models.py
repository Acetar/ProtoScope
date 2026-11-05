"""
动画 props 的 Python 侧契约。

与 renderer/src/schema/animation.ts 里的 Zod schema 一一对应：
- 这里负责"生成阶段"的校验（给出人能看懂的报错，能定位到具体字段）
- Zod 那侧负责"渲染阶段"的最后一道闸门（Node 进程里 parse 一次）

两边字段名必须一致，改结构时两边一起改。
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

IconName = Literal["laptop", "server", "cloud", "router"]


class PacketFields(BaseModel):
    seq: Optional[str] = None
    ack: Optional[str] = None
    flags: Optional[str] = None
    len: Optional[str] = None


class PacketFly(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["packet-fly"] = "packet-fly"
    from_: str = Field(alias="from")
    to: str
    label: str
    delay: int = Field(ge=0)
    durationInFrames: int = Field(gt=0)
    fields: PacketFields
    color: str


class StateChange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["state-change"] = "state-change"
    actor: str
    from_: str = Field(alias="from")
    to: str
    delay: int = Field(ge=0)


class Pulse(BaseModel):
    type: Literal["pulse"] = "pulse"
    actor: str
    delay: int = Field(ge=0)


class Callout(BaseModel):
    type: Literal["callout"] = "callout"
    actor: str
    text: str
    delay: int = Field(ge=0)


Action = Annotated[
    Union[PacketFly, StateChange, Pulse, Callout],
    Field(discriminator="type"),
]


class Scene(BaseModel):
    id: str
    title: str
    startFrame: int = Field(ge=0)
    durationInFrames: int = Field(gt=0)
    narration: str
    actions: list[Action]


class Actor(BaseModel):
    id: str
    label: str
    icon: IconName
    x: float
    y: float
    initialState: str


class Caption(BaseModel):
    startFrame: int = Field(ge=0)
    endFrame: int = Field(ge=0)
    text: str


class AnimationProps(BaseModel):
    knowledgePoint: str
    templateId: str
    title: str
    subtitle: str
    fps: Literal[30] = 30
    width: Literal[1920] = 1920
    height: Literal[1080] = 1080
    totalFrames: int = Field(gt=0)
    actors: list[Actor] = Field(min_length=2)
    scenes: list[Scene] = Field(min_length=1)
    captions: list[Caption]
    audioSrc: Optional[str] = None

    @model_validator(mode="after")
    def _check_timeline(self) -> "AnimationProps":
        """结构合法不等于时间线合法，这里补三类跨字段检查。"""
        actor_ids = {a.id for a in self.actors}
        if len(actor_ids) != len(self.actors):
            raise ValueError("actors 的 id 必须唯一")

        prev_end = 0
        for i, scene in enumerate(self.scenes):
            if scene.startFrame < prev_end:
                raise ValueError(
                    f"scenes[{i}] 起点 {scene.startFrame} 早于上一场景结束 {prev_end}，时间线重叠"
                )
            prev_end = scene.startFrame + scene.durationInFrames
            if prev_end > self.totalFrames:
                raise ValueError(
                    f"scenes[{i}] 结束于 {prev_end}，超出 totalFrames={self.totalFrames}"
                )

            for j, act in enumerate(scene.actions):
                where = f"scenes[{i}].actions[{j}]"
                if isinstance(act, PacketFly):
                    if act.from_ not in actor_ids:
                        raise ValueError(f"{where} 的 from={act.from_!r} 不在 actors 里")
                    if act.to not in actor_ids:
                        raise ValueError(f"{where} 的 to={act.to!r} 不在 actors 里")
                    if act.from_ == act.to:
                        raise ValueError(f"{where} 的 from 与 to 相同，报文没有飞行方向")
                    if act.delay + act.durationInFrames > scene.durationInFrames:
                        raise ValueError(
                            f"{where} 在场景内放不下：delay({act.delay}) + "
                            f"duration({act.durationInFrames}) > {scene.durationInFrames}"
                        )
                elif isinstance(act, (StateChange, Pulse, Callout)):
                    if act.actor not in actor_ids:
                        raise ValueError(f"{where} 的 actor={act.actor!r} 不在 actors 里")
                    if act.delay > scene.durationInFrames:
                        raise ValueError(f"{where} 的 delay 超出场景时长")

        for i, cap in enumerate(self.captions):
            if cap.endFrame <= cap.startFrame:
                raise ValueError(f"captions[{i}] 的 endFrame 必须大于 startFrame")
            if cap.endFrame > self.totalFrames:
                raise ValueError(f"captions[{i}] 的时间区间超出 totalFrames")

        return self


# ---------- 接口出入参 ----------

class KnowledgePoint(BaseModel):
    id: str
    title: str
    summary: str
    aliases: list[str]
    actors: list[str]


class GenerateRequest(BaseModel):
    """用户需求。topic 传目录 id，或 prompt 传自由描述（两者至少一个）。"""
    topic: Optional[str] = None
    prompt: Optional[str] = None
    durationSec: int = Field(default=18, ge=8, le=40)

    @model_validator(mode="after")
    def _one_of(self) -> "GenerateRequest":
        if not (self.topic or self.prompt):
            raise ValueError("topic 与 prompt 至少提供一个")
        return self


class GenerateMeta(BaseModel):
    source: Literal["catalog", "llm"]
    knowledgePoint: str
    durationSec: float
    totalFrames: int
    elapsedMs: int
    notes: list[str] = []


class GenerateResponse(BaseModel):
    props: AnimationProps
    meta: GenerateMeta


class RenderRequest(BaseModel):
    props: AnimationProps


class RenderJob(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "failed"]
    url: Optional[str] = None
    error: Optional[str] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None

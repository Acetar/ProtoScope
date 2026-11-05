"""
规则库的构造助手。

每个知识点的剧本只写"语义"（谁在第几个场景、发什么报文、状态怎么变），
时间轴（startFrame / totalFrames / delay 偏移）由这里统一算出来，
避免每个剧本各写一套容易错的时间计算。
"""
from __future__ import annotations

from typing import Optional, Sequence

DEFAULT_SCENE_FRAMES = 180
FPS = 30

COLORS = {
    "warm": "#ffb454",
    "cool": "#38e1ff",
    "green": "#3ddc97",
    "red": "#ff6b6b",
    "purple": "#b39ddb",
}


def actor(
    id: str,
    label: str,
    icon: str,
    x: float,
    y: float = 250,
    initial: str = "READY",
) -> dict:
    return {
        "id": id,
        "label": label,
        "icon": icon,
        "x": x,
        "y": y,
        "initialState": initial,
    }


def packet(
    who_from: str,
    who_to: str,
    label: str,
    at: float,
    dur: int = 60,
    seq: Optional[str] = None,
    ack: Optional[str] = None,
    flags: Optional[str] = None,
    length: Optional[str] = None,
    color: str = "warm",
    extra: Optional[dict] = None,
) -> dict:
    """at: 本条报文在自己的场景里从第几帧起飞（相对场景起点）。

    extra: 额外的字段行（真实抓包翻译时会带上 ip.src / tcp.window 等原始字段）。
    """
    fields: dict[str, str] = {}
    if seq is not None:
        fields["seq"] = seq
    if ack is not None:
        fields["ack"] = ack
    if flags is not None:
        fields["flags"] = flags
    if length is not None:
        fields["len"] = length
    if extra:
        fields.update({k: v for k, v in extra.items() if v})
    return {
        "type": "packet-fly",
        "from": who_from,
        "to": who_to,
        "label": label,
        "delay": int(at),
        "durationInFrames": dur,
        "fields": fields,
        "color": COLORS.get(color, color),
    }


def state(actor_id: str, frm: str, to: str, at: float) -> dict:
    return {
        "type": "state-change",
        "actor": actor_id,
        "from": frm,
        "to": to,
        "delay": int(at),
    }


def pulse(actor_id: str, at: float) -> dict:
    return {"type": "pulse", "actor": actor_id, "delay": int(at)}


def callout(actor_id: str, text: str, at: float) -> dict:
    return {"type": "callout", "actor": actor_id, "text": text, "delay": int(at)}


def scene(
    sid: str,
    title: str,
    narration: str,
    actions: Sequence[dict],
    caption: str,
    frames: int = DEFAULT_SCENE_FRAMES,
) -> dict:
    """一个场景 = 一屏讲解 + 一组动作 + 一条底部字幕。"""
    return {
        "id": sid,
        "title": title,
        "narration": narration,
        "actions": list(actions),
        "frames": frames,
        "caption": caption,
    }


def compile_props(
    knowledge_point: str,
    title: str,
    subtitle: str,
    actors: Sequence[dict],
    scenes: Sequence[dict],
    template_id: str = "ProtocolFlow",
) -> dict:
    """
    把剧本编译成完整的 AnimationProps dict：
    场景首尾相接排时间轴，字幕取每个场景的中后段，totalFrames = 各场景之和。
    """
    out_scenes = []
    captions = []
    cursor = 0

    for s in scenes:
        frames = s["frames"]
        out_scenes.append(
            {
                "id": s["id"],
                "title": s["title"],
                "startFrame": cursor,
                "durationInFrames": frames,
                "narration": s["narration"],
                "actions": s["actions"],
            }
        )
        # 字幕：跳过入场动画，留出结尾缓冲
        cap_start = cursor + min(24, frames // 6)
        cap_end = cursor + frames - min(12, frames // 10)
        captions.append(
            {"startFrame": cap_start, "endFrame": cap_end, "text": s["caption"]}
        )
        cursor += frames

    return {
        "knowledgePoint": knowledge_point,
        "templateId": template_id,
        "title": title,
        "subtitle": subtitle,
        "fps": FPS,
        "width": 1920,
        "height": 1080,
        "totalFrames": cursor,
        "actors": list(actors),
        "scenes": out_scenes,
        "captions": captions,
        "audioSrc": None,
    }


def scale(props: dict, factor: float) -> dict:
    """
    按比例重排时间轴，用于"用户要求 12s / 24s"这种时长定制。
    所有帧数至少保留 1 帧，报文飞行不短于 18 帧（否则看起来是闪现）。
    """
    if abs(factor - 1.0) < 1e-3:
        return props

    def s(v: float, floor: int = 1) -> int:
        return max(floor, int(round(v * factor)))

    scenes = []
    for sc in props["scenes"]:
        dur = s(sc["durationInFrames"], 30)
        actions = []
        for act in sc["actions"]:
            a = dict(act)
            a["delay"] = s(act["delay"], 0)
            if "durationInFrames" in a:
                a["durationInFrames"] = s(a["durationInFrames"], 18)
            actions.append(a)
        # 缩放后动作可能放不下：把场景撑到刚好容纳最后一个动作
        for a in actions:
            needed = a["delay"] + a.get("durationInFrames", 1)
            if needed > dur:
                dur = needed
        scenes.append({**sc, "durationInFrames": dur, "actions": actions})

    cursor = 0
    for sc in scenes:
        sc["startFrame"] = cursor
        cursor += sc["durationInFrames"]

    # 字幕：一条场景对应一条字幕时按序重贴边；否则整条时间轴一起缩放
    old_captions = props["captions"]
    if len(old_captions) == len(scenes):
        captions = [
            {
                "startFrame": sc["startFrame"] + min(24, sc["durationInFrames"] // 6),
                "endFrame": sc["startFrame"]
                + sc["durationInFrames"]
                - min(12, sc["durationInFrames"] // 10),
                "text": old["text"],
            }
            for sc, old in zip(scenes, old_captions)
        ]
    else:
        captions = [
            {
                "startFrame": s(cap["startFrame"], 0),
                "endFrame": s(cap["endFrame"], 1),
                "text": cap["text"],
            }
            for cap in old_captions
        ]

    return {**props, "totalFrames": cursor, "scenes": scenes, "captions": captions}

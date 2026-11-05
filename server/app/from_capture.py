"""把一段真实抓包的会话，翻译成 AnimationProps。

这是"同一个渲染器两个入口"的第二个入口：
- 入口 A：知识点 → 规则库/大模型 → props（planner.py）
- 入口 B：真实 pcap → 选一个会话 → props（本文件）

翻译规则（样板化，不做语义推断）：
- 两个通信主体 → 左右两张演员卡（源 = 客户端，目的 = 服务端）；
- 每条报文 → 一个场景 + 一条 packet-fly；超过 6 条报文时只取前 6 条，
  其余在旁白里说明"共 N 个报文"；
- 字幕直接取报文的 summary（如 "SYN 51234 → 80"），
  旁白把 flags / seq / ack / 应用层请求行拼成一句人话。
"""
from __future__ import annotations

from typing import Any

from .builders import actor, compile_props, packet, scene

MAX_MESSAGES = 6


def _narration(p: dict[str, Any]) -> str:
    """把一条报文写成一句中文，尽量说清"谁对谁做了什么"。"""
    f = p["fields"]
    proto = p["proto"]
    parts: list[str] = []

    if proto == "ARP":
        op = f.get("arp.op", "")
        if op == "request":
            return f"{p['src']} 广播询问：{p['dst']} 的 MAC 地址是多少？"
        return f"{p['dst']} 回答：{p['dst']} 在 {f.get('eth.src', '某个 MAC')}。"

    if proto == "TCP":
        flags = f.get("tcp.flags", "")
        if flags == "SYN":
            parts.append(f"发起连接，SYN 携带初始序号 seq={f.get('tcp.seq', '?')}")
        elif flags == "SYN, ACK":
            parts.append(
                f"同意建连：seq={f.get('tcp.seq', '?')}、ack={f.get('tcp.ack', '?')}，"
                "一个报文同时承担确认和声明两个语义"
            )
        elif flags == "ACK" and not p.get("payloadLen"):
            parts.append(f"确认收到，ack={f.get('tcp.ack', '?')}")
        elif "FIN" in flags:
            parts.append("请求关闭连接（FIN），本方向不再发送数据")
        elif "RST" in flags:
            parts.append("发送 RST，直接重置连接")
        else:
            parts.append(f"携带 {p.get('payloadLen', 0)} 字节数据，序号 seq={f.get('tcp.seq', '?')}")
    elif proto == "UDP":
        parts.append(f"UDP 报文，{p.get('payloadLen', 0)} 字节载荷")
    elif proto == "ICMP":
        parts.append(f"ICMP type={f.get('icmp.type', '?')}")
    else:
        parts.append("其他协议报文")

    if "http.request.method" in f:
        parts.append(f"请求行 {f['http.request.method']} {f.get('http.request.uri', '/')}")
    elif "http.response.code" in f:
        parts.append(f"响应码 {f['http.response.code']}")

    # 端点信息不再拼进旁白：演员卡上已经写着 10.0.0.5:51234 / 93.184.216.34:80，
    # 旁白再念一遍只会让人分心。

    return "；".join(parts) + "。"


def _packet_label(p: dict[str, Any]) -> str:
    """报文胶囊上的字，越短越好（画面上只有 ~150px）。"""
    f = p["fields"]
    if p["proto"] == "ARP":
        return "ARP 请求" if f.get("arp.op") == "request" else "ARP 应答"
    if "http.request.method" in f:
        return f"{f['http.request.method']} {f.get('http.request.uri', '/')}"[:22]
    if "http.response.code" in f:
        return f"HTTP {f['http.response.code']}"
    flags = f.get("tcp.flags", "")
    return flags or p["proto"]


def build_from_capture(
    session: dict[str, Any],
    packets: list[dict[str, Any]],
    duration_sec: float = 12,
) -> dict:
    """返回 AnimationProps dict（未经 pydantic 校验，调用方负责）。"""
    chosen = [p for p in packets if p.get("sessionId") == session["id"]][:MAX_MESSAGES]
    if not chosen:
        raise ValueError("这个会话里没有报文。")

    client = session["client"]
    server = session["server"]
    client_port = session.get("clientPort")
    server_port = session.get("serverPort")

    client_label = f"{client}" + (f":{client_port}" if client_port else "")
    server_label = f"{server}" + (f":{server_port}" if server_port else "")

    actors = [
        actor("client", client_label, "laptop", 300, 250, "就绪"),
        actor("server", server_label, "server", 1000, 250, "就绪"),
    ]

    scenes = []
    for i, p in enumerate(chosen, start=1):
        outbound = p["src"] == client
        src_id, dst_id = ("client", "server") if outbound else ("server", "client")
        fields = {k: v for k, v in p["fields"].items() if k.startswith(("tcp.", "http.", "udp.", "arp."))}
        fields["frame.number"] = str(p["index"])
        scenes.append(
            scene(
                f"cap-{i}",
                f"第 {i} 个报文 · {p['time']}",
                _narration(p),
                [
                    packet(
                        src_id,
                        dst_id,
                        _packet_label(p),
                        at=18,
                        seq=fields.get("tcp.seq", ""),
                        ack=fields.get("tcp.ack", ""),
                        flags=fields.get("tcp.flags", ""),
                        color="warm" if outbound else "cool",
                        extra=fields,
                    )
                ],
                f"{p['summary']}",
            )
        )

    total = len([p for p in packets if p.get("sessionId") == session["id"]])
    subtitle = f"真实抓包 · {session['label']} · 共 {total} 个报文"
    if total > MAX_MESSAGES:
        subtitle += f"（画面展示前 {MAX_MESSAGES} 个）"

    props = compile_props(
        knowledge_point=f"capture.{session['id']}",
        title=session["label"],
        subtitle=subtitle,
        actors=actors,
        scenes=scenes,
    )

    # 按请求时长等比缩放（编译出来的默认长度和 12s 不一定一致）
    from .builders import scale

    natural = props["totalFrames"] / props["fps"]
    if duration_sec and abs(duration_sec - natural) > 0.5:
        props = scale(props, duration_sec / natural)

    return props

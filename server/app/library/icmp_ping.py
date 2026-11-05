"""ICMP Echo：ping 到底在测什么。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("host", "本机", "laptop", 300, 250, "READY"),
        actor("target", "目标主机", "server", 1000, 250, "READY"),
    ]

    scenes = [
        scene(
            "scene-1",
            "Echo Request · type 8",
            "ping 发的是一整个 ICMP 报文，不是 TCP 也不是 UDP：type=8 表示「请求你回一个」。"
            "顺手带上 TTL=64，每经过一个路由器减 1，所以回来的 TTL 能反推跳数。",
            [
                pulse("host", 6),
                packet(
                    "host", "target", "Echo Request", at=20, dur=60,
                    flags="type=8", length="98", color="warm",
                    extra={"icmp.type": "8", "icmp.code": "0", "ip.ttl": "64", "icmp.seq": "1"},
                ),
            ],
            "① 发出 ICMP type=8 Echo Request，TTL=64",
        ),
        scene(
            "scene-2",
            "Echo Reply · type 0",
            "目标收到后原样回一个 type=0。报文内容和请求几乎一样，"
            "所以主机能靠序号把「哪一个请求的回复」对上。这一去一回的时间就是 RTT。",
            [
                packet(
                    "target", "host", "Echo Reply", at=30, dur=60,
                    flags="type=0", length="98", color="green",
                    extra={"icmp.type": "0", "icmp.code": "0", "ip.ttl": "57", "icmp.seq": "1"},
                ),
                callout("host", "RTT ≈ 12 ms", 120),
            ],
            "② 回 type=0，TTL 从 64 降到 57 → 中间约 7 跳",
        ),
        scene(
            "scene-3",
            "连续发四个 · 看丢包与抖动",
            "ping 默认连发 4 个。每个请求换一个序号，统计里就能给出「几发几收、平均 RTT、抖动」。"
            "如果全丢，说明对方禁了 ICMP 或者路径不通——注意有些服务器只是不答 ping，服务照样是通的。",
            [
                packet("host", "target", "request #2", at=16, dur=52,
                       flags="type=8", length="98", color="warm",
                       extra={"icmp.seq": "2", "ip.ttl": "64"}),
                packet("target", "host", "reply #2", at=80, dur=52,
                       flags="type=0", length="98", color="green",
                       extra={"icmp.seq": "2", "ip.ttl": "57"}),
                callout("host", "4 发 4 收 · 平均 12 ms", 150),
            ],
            "③ 连发 4 个，靠序号配对，统计丢包与 RTT",
        ),
    ]

    return compile_props(
        "icmp.ping",
        "ICMP 与 ping",
        "一条 ping 命令，实际测到了什么？",
        actors,
        scenes,
    )

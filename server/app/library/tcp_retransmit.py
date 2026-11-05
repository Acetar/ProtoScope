"""TCP 超时重传：丢了一个包，连接靠什么自己扛过去。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("client", "发送方", "laptop", 300, 250, "ESTABLISHED"),
        actor("server", "接收方", "server", 1000, 250, "ESTABLISHED"),
    ]

    scenes = [
        scene(
            "scene-1",
            "发出数据段 · DATA",
            "发送方把 500 字节装进一个段。seq=1001 的意思是「这段数据从第 1001 号字节开始」，"
            "ack=401 是在顺带确认对方的字节。发出之后立刻启动重传定时器，超过 RTO 没等到确认就重发。",
            [
                pulse("client", 6),
                packet(
                    "client", "server", "DATA", at=20, dur=64,
                    seq="1001", ack="401", flags="PSH, ACK", length="500", color="warm",
                ),
                callout("client", "启动 RTO 定时器", 96),
            ],
            "① 发送 seq=1001 len=500，并启动重传定时器",
        ),
        scene(
            "scene-2",
            "定时器到期 · 没有 ACK",
            "这段数据在路上丢了，接收方根本没收到，自然不会有 ACK。"
            "RTO 到期后，发送方把拥塞窗口减半、把 RTO 翻倍（指数退避），然后重发同一段——"
            "注意 seq 还是 1001，因为对端确实没收到过。",
            [
                callout("client", "RTO 到期，重传", 20),
                callout("server", "什么都没收到", 20),
            ],
            "② RTO 到期：拥塞窗口减半、RTO 翻倍，重发同一段",
        ),
        scene(
            "scene-3",
            "重传成功 · ACK 1501",
            "这一次到了。接收方回 ACK=1501，意思是「1001 到 1500 这 500 字节我都收到了，下一个我要 1501」。"
            "发送方收到后把定时器清掉，继续往下发。",
            [
                packet(
                    "client", "server", "DATA(重传)", at=20, dur=64,
                    seq="1001", ack="401", flags="PSH, ACK", length="500", color="red",
                ),
                packet(
                    "server", "client", "ACK", at=100, dur=56,
                    seq="401", ack="1501", flags="ACK", length="0", color="green",
                ),
                callout("client", "定时器清零", 160),
            ],
            "③ 重传到达，ACK=1501 确认 500 字节全部收下",
        ),
    ]

    return compile_props(
        "tcp.retransmit",
        "TCP 超时重传",
        "丢包之后，连接凭什么自己恢复？",
        actors,
        scenes,
    )

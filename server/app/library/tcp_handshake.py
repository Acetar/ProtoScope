"""TCP 三次握手：最经典的"为什么是三次不是两次"。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene, state


def build() -> dict:
    actors = [
        actor("client", "客户端", "laptop", 300, 250, "CLOSED"),
        actor("server", "服务端", "server", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "第一次握手 · SYN",
            "客户端想建连接，先发一个 SYN，带上自己的初始序号 ISN(c)=100。"
            "此时它还无法确认服务端是否在线、是否愿意接收。",
            [
                pulse("client", 6),
                packet("client", "server", "SYN", at=20, seq="100", flags="SYN", color="warm"),
                state("client", "CLOSED", "SYN_SENT", 20),
            ],
            "① 客户端发送 SYN，声明自己的初始序号 seq=100",
        ),
        scene(
            "scene-2",
            "第二次握手 · SYN + ACK",
            "服务端收到了，回一个 SYN+ACK：既确认对方的 100（ack=101），"
            "又声明自己的初始序号 ISN(s)=300。一个报文承担两个语义，这是三次握手的核心。",
            [
                packet(
                    "server", "client", "SYN + ACK", at=20,
                    seq="300", ack="101", flags="SYN, ACK", color="cool",
                ),
                state("server", "LISTEN", "SYN_RCVD", 20),
            ],
            "② 服务端回 SYN+ACK：确认 101，同时声明 seq=300",
        ),
        scene(
            "scene-3",
            "第三次握手 · ACK",
            "客户端确认 300（ack=301），双方进入 ESTABLISHED。"
            "第三次握手的真正作用，是让服务端确认「客户端确实收到了我的 SYN」，"
            "否则服务端无法区分「旧连接的延迟报文」和「新的建连请求」。",
            [
                packet(
                    "client", "server", "ACK", at=20,
                    seq="101", ack="301", flags="ACK", color="green",
                ),
                state("client", "SYN_SENT", "ESTABLISHED", 84),
                state("server", "SYN_RCVD", "ESTABLISHED", 84),
            ],
            "③ 客户端回 ACK：确认 301，连接建立",
        ),
    ]

    return compile_props(
        "tcp.handshake",
        "TCP 三次握手",
        "为什么建立连接需要三个来回？",
        actors,
        scenes,
    )

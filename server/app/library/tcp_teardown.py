"""TCP 四次挥手：为什么断开比建立多一次。"""
from ..builders import actor, compile_props, packet, scene, state


def build() -> dict:
    actors = [
        actor("client", "主动关闭方", "laptop", 300, 250, "ESTABLISHED"),
        actor("server", "被动关闭方", "server", 1000, 250, "ESTABLISHED"),
    ]

    scenes = [
        scene(
            "scene-1",
            "第一次挥手 · FIN",
            "客户端数据发完了，发 FIN 表示「我没有数据要发了」，"
            "但它仍然可以继续接收数据——TCP 是全双工的，两个方向要分别关闭。",
            [
                packet("client", "server", "FIN", at=18, seq="201", flags="FIN, ACK", color="warm", dur=54),
                state("client", "ESTABLISHED", "FIN_WAIT_1", 18),
            ],
            "① 客户端发 FIN：我不再发送数据了",
            frames=150,
        ),
        scene(
            "scene-2",
            "第二次挥手 · ACK",
            "服务端先回 ACK 确认收到 FIN，进入 CLOSE_WAIT。"
            "此时连接处于「半关闭」：客户端不再发，服务端还能把剩余数据发完。",
            [
                packet("server", "client", "ACK", at=18, seq="501", ack="202", flags="ACK", color="cool", dur=54),
                state("server", "ESTABLISHED", "CLOSE_WAIT", 18),
                state("client", "FIN_WAIT_1", "FIN_WAIT_2", 72),
            ],
            "② 服务端回 ACK：确认收到，进入半关闭",
            frames=150,
        ),
        scene(
            "scene-3",
            "第三次挥手 · FIN",
            "服务端把剩下的数据发完，也发一个 FIN 表示「我也发完了」。"
            "这就是四次挥手比三次握手多一次的原因：两个方向各关一次，且不能合并。",
            [
                packet("server", "client", "FIN", at=18, seq="501", ack="202", flags="FIN, ACK", color="purple", dur=54),
                state("server", "CLOSE_WAIT", "LAST_ACK", 18),
            ],
            "③ 服务端数据发完，也发 FIN",
            frames=150,
        ),
        scene(
            "scene-4",
            "第四次挥手 · ACK + TIME_WAIT",
            "客户端回 ACK 确认，自己进入 TIME_WAIT 并等 2MSL 才真正关闭。"
            "这个等待是为了两件事：让最后的 ACK 有机会重传，以及让旧连接的残留报文在网络中自然消亡。",
            [
                packet("client", "server", "ACK", at=18, seq="202", ack="502", flags="ACK", color="green", dur=54),
                state("client", "FIN_WAIT_2", "TIME_WAIT", 18),
                state("server", "LAST_ACK", "CLOSED", 72),
            ],
            "④ 客户端回 ACK，等 2MSL 后关闭",
            frames=170,
        ),
    ]

    return compile_props(
        "tcp.teardown",
        "TCP 四次挥手",
        "断开连接为什么要四个报文？",
        actors,
        scenes,
    )

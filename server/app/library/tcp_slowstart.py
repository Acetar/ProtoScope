"""TCP 慢启动与拥塞避免：窗口是怎么一点点涨上去的。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("client", "发送方", "laptop", 300, 250, "cwnd=1"),
        actor("server", "接收方", "server", 1000, 250, "ESTABLISHED"),
    ]

    scenes = [
        scene(
            "scene-1",
            "第一个往返 · cwnd = 1",
            "连接刚建立，拥塞窗口 cwnd 只有 1 个 MSS（约 1460 字节）。"
            "发送方一次只能发一段，发完必须等确认——这时候它完全不知道链路能承受多少，只能小心试探。",
            [
                pulse("client", 6),
                packet(
                    "client", "server", "DATA", at=20, dur=60,
                    seq="1", ack="1", flags="PSH, ACK", length="1460", color="warm",
                ),
                packet(
                    "server", "client", "ACK", at=92, dur=56,
                    seq="1", ack="1461", flags="ACK", length="0", color="green",
                ),
                callout("client", "cwnd 1 → 2", 150),
            ],
            "① 一次发 1 个 MSS，收到 ACK 后 cwnd 翻倍",
        ),
        scene(
            "scene-2",
            "每个 RTT 翻一倍 · 指数增长",
            "每收到一个确认，cwnd 就加 1 个 MSS——于是一个往返之后能发 2 段、再一个往返能发 4 段。"
            "这就是「慢启动」这个名字的误导之处：起点慢，增长其实是指数的。",
            [
                packet("client", "server", "DATA 1", at=16, dur=52,
                       seq="1461", ack="1", flags="PSH, ACK", length="1460", color="warm"),
                packet("client", "server", "DATA 2", at=84, dur=52,
                       seq="2921", ack="1", flags="PSH, ACK", length="1460", color="warm"),
                packet("server", "client", "ACK", at=152, dur=50,
                       seq="1", ack="4381", flags="ACK", length="0", color="green"),
                callout("client", "cwnd 2 → 4", 190),
            ],
            "② 一个 RTT 内连发 2 段，cwnd 涨到 4",
        ),
        scene(
            "scene-3",
            "碰到 ssthresh · 转为线性增长",
            "窗口涨到慢启动阈值 ssthresh 就不再翻倍了，改成每个 RTT 只加 1 个 MSS，"
            "这一段叫拥塞避免。一旦真的丢包，ssthresh 减半、窗口退回 1，重新开始试探。",
            [
                packet("client", "server", "DATA × 4", at=16, dur=60,
                       seq="4381", ack="1", flags="PSH, ACK", length="5840", color="cool"),
                packet("server", "client", "ACK", at=110, dur=50,
                       seq="1", ack="10221", flags="ACK", length="0", color="green"),
                callout("client", "ssthresh 已到：改为 +1/RTT", 160),
            ],
            "③ 到达 ssthresh 后线性增长，丢包则窗口减半",
        ),
    ]

    return compile_props(
        "tcp.slowstart",
        "TCP 慢启动与拥塞避免",
        "窗口为什么要先指数、后线性地涨？",
        actors,
        scenes,
    )

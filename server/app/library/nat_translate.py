"""NAT 地址转换：一台路由器怎么让十几台内网机器同时上网。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("host", "内网主机 192.168.1.10", "laptop", 300, 250, "READY"),
        actor("web", "公网服务器 93.184.216.34", "cloud", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "出方向 · 源地址被改写",
            "内网主机用 192.168.1.10:51234 发请求。这个地址在公网上不可路由，"
            "所以路由器把它改写成自己的公网地址 203.0.113.7:62001，并记下这条映射。"
            "端口号是路由器的关键手段：一个公网 IP 靠不同端口区分不同内网连接。",
            [
                pulse("host", 6),
                packet(
                    "host", "web", "GET /", at=20, dur=64,
                    seq="1", ack="1", flags="PSH, ACK", length="512", color="warm",
                    extra={"ip.src": "203.0.113.7", "tcp.sport": "62001",
                           "tcp.dport": "80", "nat.original": "192.168.1.10:51234"},
                ),
                callout("host", "NAT 表：51234 → 62001", 120),
            ],
            "① 源地址改写为公网 203.0.113.7:62001，写入 NAT 表",
        ),
        scene(
            "scene-2",
            "回方向 · 目的地址被查表还原",
            "服务器只认识 203.0.113.7:62001，回包就发到这儿。路由器收到后查 NAT 表，"
            "把这个端口的包还原成 192.168.1.10:51234 再交给内网主机——反向也必须改，否则回包进不来。",
            [
                packet(
                    "web", "host", "200 OK", at=20, dur=64,
                    seq="1", ack="513", flags="PSH, ACK", length="1400", color="green",
                    extra={"ip.dst": "203.0.113.7", "tcp.sport": "80",
                           "tcp.dport": "62001"},
                ),
                callout("host", "查表还原 → 192.168.1.10:51234", 120),
            ],
            "② 回包打到 62001，路由器查表还原给内网主机",
        ),
        scene(
            "scene-3",
            "连接结束 · 表项老化",
            "连接关掉后表项并不会立刻消失，而是等一段时间没有流量才老化删除。"
            "这也是为什么内网服务默认「外面连不进来」：没有表项，就没有路。"
            "要让外面主动连进来，得手动做端口映射（DNAT）。",
            [
                packet("host", "web", "FIN, ACK", at=20, dur=56,
                       seq="513", ack="1401", flags="FIN, ACK", length="0", color="purple"),
                callout("host", "表项超时后删除", 120),
            ],
            "③ 连接关闭，NAT 表项超时老化；外部主动连入需端口映射",
        ),
    ]

    return compile_props(
        "nat.translate",
        "NAT 地址转换",
        "一个公网 IP，怎么撑起一整个内网？",
        actors,
        scenes,
    )

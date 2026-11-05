"""DHCP 四步：插上网线之后，地址是怎么自己来的。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("host", "新接入主机", "laptop", 300, 250, "0.0.0.0"),
        actor("dhcp", "DHCP 服务器", "server", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "DISCOVER · 我还什么都没有",
            "主机刚接入，连自己的 IP 都不知道，只能从 0.0.0.0 向 255.255.255.255 广播："
            "「附近有没有 DHCP 服务器？」广播的意义是——它没法指定收件人，只能让所有人听见。",
            [
                pulse("host", 6),
                packet(
                    "host", "dhcp", "DISCOVER", at=20, dur=64,
                    flags="broadcast", length="342", color="warm",
                    extra={"dhcp.msgtype": "1", "udp.srcport": "68", "udp.dstport": "67",
                           "ip.src": "0.0.0.0", "ip.dst": "255.255.255.255"},
                ),
            ],
            "① 0.0.0.0:68 → 255.255.255.255:67 广播 DISCOVER",
        ),
        scene(
            "scene-2",
            "OFFER · 我给你留了一个",
            "服务器从地址池里挑一个空闲地址（比如 192.168.1.50），连同网关、DNS、租期一起提议回来。"
            "这时地址还没生效——别人也可能同时提议，主机要自己选一个。",
            [
                packet(
                    "dhcp", "host", "OFFER", at=20, dur=64,
                    flags="unicast", length="342", color="cool",
                    extra={"dhcp.msgtype": "2", "dhcp.yiaddr": "192.168.1.50",
                           "dhcp.lease": "86400"},
                ),
                callout("host", "收到提议，先不配置", 110),
            ],
            "② 服务器 OFFER：192.168.1.50，租期 24 小时",
        ),
        scene(
            "scene-3",
            "REQUEST + ACK · 正式生效",
            "主机广播 REQUEST 明确说「我要 192.168.1.50」，顺便告诉其他服务器别留了。"
            "服务器回 ACK 才算生效。之所以还要广播一次，是因为可能有多个服务器都提了议。",
            [
                packet("host", "dhcp", "REQUEST", at=20, dur=58,
                       flags="broadcast", length="342", color="warm",
                       extra={"dhcp.msgtype": "3", "dhcp.requested": "192.168.1.50"}),
                packet("dhcp", "host", "ACK", at=96, dur=56,
                       flags="unicast", length="342", color="green",
                       extra={"dhcp.msgtype": "5", "dhcp.yiaddr": "192.168.1.50"}),
                callout("host", "地址可用 · 开始计时租期", 164),
            ],
            "③ REQUEST 广播 + ACK 确认，地址才真正可用",
        ),
    ]

    return compile_props(
        "dhcp.acquire",
        "DHCP 动态获取地址",
        "插上网线就能上网，中间发生了什么？",
        actors,
        scenes,
    )

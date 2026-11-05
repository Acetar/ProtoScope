"""ARP 地址解析：同一个局域网里，IP 怎么找到 MAC。"""
from ..builders import actor, callout, compile_props, packet, scene, state


def build() -> dict:
    actors = [
        actor("host", "主机 192.168.1.10", "laptop", 300, 250, "READY"),
        actor("gateway", "网关 192.168.1.1", "router", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "ARP 请求（广播）",
            "主机要发数据给 192.168.1.1，但它只知道 IP，不知道对方的 MAC。"
            "于是发一个 ARP 请求，目标 MAC 填全 F 的广播地址，问「谁是 192.168.1.1？」",
            [
                packet(
                    "host", "gateway", "ARP Request（广播）", at=18,
                    length="42", color="warm", dur=66,
                ),
                callout("host", "谁是 192.168.1.1？", 96),
                state("host", "READY", "ARP_REQUESTING", 18),
            ],
            "① 主机广播 ARP 请求：谁是 192.168.1.1？",
            frames=160,
        ),
        scene(
            "scene-2",
            "ARP 应答（单播）",
            "网关发现问的是自己，单播回一个 ARP Reply，"
            "把自己的 MAC 地址告诉主机。注意：请求是广播，应答是单播，"
            "否则整个局域网都要为一次解析买单。",
            [
                packet(
                    "gateway", "host", "ARP Reply", at=18,
                    length="42", color="cool", dur=60,
                ),
                callout("gateway", "我的 MAC 是 00:1a:2b:3c:4d:5e", 90),
                state("gateway", "LISTEN", "REPLIED", 18),
            ],
            "② 网关单播应答，告知自己的 MAC 地址",
            frames=160,
        ),
        scene(
            "scene-3",
            "写入缓存，开始发包",
            "主机把这对 IP→MAC 写进 ARP 缓存（通常几分钟过期），"
            "然后把 IP 包封装进以太网帧发出去。"
            "所以每换一个网段，都要重新做一次 ARP。",
            [
                packet(
                    "host", "gateway", "Ethernet Frame（IP 包）", at=18,
                    length="1514", color="green", dur=66,
                ),
                state("host", "ARP_REQUESTING", "SENDING", 96),
            ],
            "③ 缓存映射，封装成以太网帧发出",
            frames=160,
        ),
    ]

    return compile_props(
        "arp.resolve",
        "ARP 地址解析",
        "IP 地址怎么找到网卡的 MAC？",
        actors,
        scenes,
    )

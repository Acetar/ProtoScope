"""DNS 迭代查询：本地 DNS 自己跑腿，把答案一层层问出来。"""
from ..builders import actor, callout, compile_props, packet, pulse, scene


def build() -> dict:
    actors = [
        actor("local", "本地 DNS", "server", 300, 250, "READY"),
        actor("authority", "根 / 权威服务器", "cloud", 1000, 250, "READY"),
    ]

    scenes = [
        scene(
            "scene-1",
            "问根服务器 · .com 谁管",
            "本地 DNS 先问根服务器「www.example.com 是谁」。根不负责具体域名，"
            "但它知道 .com 这一层的权威服务器地址，于是把地址回给本地 DNS——这叫迭代查询，"
            "根只指路，不代跑。",
            [
                pulse("local", 6),
                packet("local", "authority", "查询 A ?", at=20, dur=60,
                       flags="QR=0", length="31", color="warm",
                       extra={"dns.qname": "www.example.com", "dns.type": "A"}),
                packet("authority", "local", "引荐 .com", at=96, dur=58,
                       flags="QR=1", length="128", color="cool",
                       extra={"dns.answer": "a.gtld-servers.net", "dns.type": "NS"}),
                callout("local", "记下 .com 的地址", 160),
            ],
            "① 根服务器只回「.com 归谁管」，不直接给答案",
        ),
        scene(
            "scene-2",
            "问 .com · example.com 谁管",
            "本地 DNS 拿着地址再去问 .com 的顶级域服务器。同样是只指路："
            "它回 example.com 自己的权威服务器地址。层层下行，每一跳都必须自己再问一次。",
            [
                packet("local", "authority", "查询 A ?", at=20, dur=58,
                       flags="QR=0", length="31", color="warm",
                       extra={"dns.qname": "www.example.com", "dns.type": "A"}),
                packet("authority", "local", "引荐 example.com", at=92, dur=56,
                       flags="QR=1", length="96", color="cool",
                       extra={"dns.answer": "ns1.example.com", "dns.type": "NS"}),
            ],
            "② 顶级域服务器回 example.com 的权威服务器地址",
        ),
        scene(
            "scene-3",
            "问权威 · 拿到 A 记录",
            "权威服务器手里才有真正的记录：www.example.com → 93.184.216.34，并附上 TTL。"
            "本地 DNS 把它缓存 TTL 秒，然后才回答给最初发问的客户端。",
            [
                packet("local", "authority", "查询 A ?", at=20, dur=56,
                       flags="QR=0", length="31", color="warm",
                       extra={"dns.qname": "www.example.com", "dns.type": "A"}),
                packet("authority", "local", "A 93.184.216.34", at=90, dur=58,
                       flags="QR=1", length="59", color="green",
                       extra={"dns.answer": "93.184.216.34", "dns.ttl": "3600"}),
                callout("local", "缓存 TTL=3600s", 158),
            ],
            "③ 权威服务器给出 A 记录，本地 DNS 缓存后再答复客户端",
        ),
    ]

    return compile_props(
        "dns.iterative",
        "DNS 迭代查询",
        "根、顶级域、权威，为什么要一个个问过去？",
        actors,
        scenes,
    )

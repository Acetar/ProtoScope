"""DNS 递归查询：一次域名解析真正走了几步。"""
from ..builders import actor, callout, compile_props, packet, scene, state


def build() -> dict:
    actors = [
        actor("client", "客户端", "laptop", 300, 250, "READY"),
        actor("resolver", "本地 DNS 服务器", "server", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "递归查询",
            "浏览器把 www.example.com 交给本地 DNS，并设置 RD=1（期望递归）。"
            "「递归」的意思是：你替我跑完全程，最后只给我一个答案。",
            [
                packet(
                    "client", "resolver", "Query: www.example.com A", at=18,
                    length="68", color="warm", dur=60,
                ),
                callout("client", "RD=1 期望递归", 96),
                state("client", "READY", "WAITING_ANSWER", 18),
            ],
            "① 客户端发起递归查询，要求给最终答案",
            frames=150,
        ),
        scene(
            "scene-2",
            "本地 DNS 迭代解析",
            "本地 DNS 自己没有缓存，就代替客户端依次去问：根服务器 → .com 顶级域 → example.com 权威服务器。"
            "这三跳对客户端是透明的，所以画面上看不到——它只等一个结果。",
            [
                callout("resolver", "根 → .com → 权威", 40),
                state("resolver", "LISTEN", "ITERATING", 30),
            ],
            "② 本地 DNS 迭代询问根、顶级域、权威服务器",
            frames=170,
        ),
        scene(
            "scene-3",
            "返回 A 记录",
            "权威服务器给出 A 记录 93.184.216.34，TTL 300 秒。"
            "本地 DNS 把它缓存下来，再回给客户端。TTL 决定了这条记录能被复用多久。",
            [
                packet(
                    "resolver", "client", "Answer: 93.184.216.34 TTL=300", at=18,
                    length="92", color="green", dur=66,
                ),
                callout("resolver", "缓存 300 秒", 96),
                state("client", "WAITING_ANSWER", "GOT_IP", 84),
            ],
            "③ 返回 A 记录，并缓存 300 秒",
            frames=160,
        ),
        scene(
            "scene-4",
            "缓存命中",
            "同一域名再次查询时，本地 DNS 直接命中缓存，几毫秒就返回，"
            "不必再走一遍根和权威。这就是 DNS 缓存对上网体验的实际影响。",
            [
                packet(
                    "client", "resolver", "Query: www.example.com A", at=14,
                    length="68", color="cool", dur=40,
                ),
                packet(
                    "resolver", "client", "Answer（cache hit）", at=68,
                    length="92", color="purple", dur=40,
                ),
                state("resolver", "ITERATING", "CACHED", 14),
            ],
            "④ 再次查询命中缓存，直接返回",
            frames=150,
        ),
    ]

    return compile_props(
        "dns.resolve",
        "DNS 递归解析",
        "输入一个域名后，解析器都做了什么？",
        actors,
        scenes,
    )

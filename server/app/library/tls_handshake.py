"""TLS 1.3 握手：从明文到加密的那四次消息。"""
from ..builders import actor, callout, compile_props, packet, scene, state


def build() -> dict:
    actors = [
        actor("client", "浏览器", "laptop", 300, 250, "CLOSED"),
        actor("server", "HTTPS 服务器", "server", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "ClientHello",
            "浏览器先发 ClientHello：支持的 TLS 版本、密码套件列表，"
            "以及一个客户端随机数和一个 X25519 公钥（key_share）。"
            "这一步是明文，因为双方还没有任何共享密钥。",
            [
                packet(
                    "client", "server", "ClientHello", at=18,
                    length="517", color="warm",
                ),
                callout("client", "random + key_share", 90),
                state("client", "CLOSED", "WAIT_SERVER_HELLO", 18),
            ],
            "① ClientHello：版本、套件、随机数与密钥份额",
            frames=160,
        ),
        scene(
            "scene-2",
            "ServerHello + 证书",
            "服务端选定套件、回自己的随机数与公钥，并附上证书链。"
            "证书的作用是让浏览器验证「这个公钥确实属于 example.com」——"
            "信任锚在系统根证书里，不在网络传输中。",
            [
                packet(
                    "server", "client", "ServerHello + Certificate", at=18,
                    length="2841", color="cool", dur=66,
                ),
                state("server", "LISTEN", "WAIT_FINISHED", 18),
            ],
            "② ServerHello + 证书链：选定套件并证明身份",
            frames=170,
        ),
        scene(
            "scene-3",
            "客户端 Finished",
            "浏览器验证证书通过，用双方公钥算出共享密钥，"
            "之后的所有消息都加密。这条 Finished 里已经带上了对整段握手记录的校验值。",
            [
                packet(
                    "client", "server", "Finished (encrypted)", at=18,
                    length="92", color="green", dur=60,
                ),
                state("client", "WAIT_SERVER_HELLO", "ESTABLISHED", 84),
            ],
            "③ Finished：验证证书、导出密钥，此后全程加密",
            frames=160,
        ),
        scene(
            "scene-4",
            "服务端 Finished",
            "服务端也回一条加密的 Finished，双方握手完成，"
            "接下来的 HTTP 请求就跑在 TLS 记录层里。"
            "TLS 1.3 把往返压到 1-RTT，会话复用时甚至可以 0-RTT。",
            [
                packet(
                    "server", "client", "Finished (encrypted)", at=18,
                    length="74", color="purple", dur=60,
                ),
                state("server", "WAIT_FINISHED", "ESTABLISHED", 84),
            ],
            "④ 服务端 Finished：握手完成，进入应用数据",
            frames=160,
        ),
    ]

    return compile_props(
        "tls.handshake",
        "TLS 1.3 握手",
        "HTTPS 的加密是怎么谈出来的？",
        actors,
        scenes,
    )

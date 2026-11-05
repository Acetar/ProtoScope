"""HTTP 请求 / 响应：一次页面打开背后的两条往返。"""
from ..builders import actor, callout, compile_props, packet, scene, state


def build() -> dict:
    actors = [
        actor("client", "浏览器", "laptop", 300, 250, "READY"),
        actor("server", "Web 服务器", "server", 1000, 250, "LISTEN"),
    ]

    scenes = [
        scene(
            "scene-1",
            "请求 HTML",
            "浏览器发 GET /index.html，带上 Host、User-Agent、Accept 等头部。"
            "HTTP 是「请求—响应」模型：服务端不会主动推，必须先有请求。",
            [
                packet(
                    "client", "server", "GET /index.html", at=18,
                    length="512", color="warm",
                ),
                callout("client", "Host / UA / Accept", 96),
                state("client", "READY", "WAITING", 18),
            ],
            "① 浏览器发 GET 请求，带上 Host 等头部",
            frames=150,
        ),
        scene(
            "scene-2",
            "响应 HTML",
            "服务端返回 200 OK 和 HTML 正文。浏览器解析 HTML，"
            "发现还要加载 /app.js 和 /style.css，于是继续发请求——页面的每个资源都是一次往返。",
            [
                packet(
                    "server", "client", "200 OK · HTML", at=18,
                    length="1.2 KB", color="cool", dur=60,
                ),
                state("client", "WAITING", "PARSING", 84),
            ],
            "② 服务端返回 200 OK + HTML 正文",
            frames=150,
        ),
        scene(
            "scene-3",
            "请求静态资源",
            "浏览器解析出引用的脚本，再发一次 GET /app.js。"
            "这也是为什么「首屏慢」常常是资源数量多，而不是单个文件大。",
            [
                packet(
                    "client", "server", "GET /app.js", at=18,
                    length="486", color="green",
                ),
                state("client", "PARSING", "FETCHING", 18),
            ],
            "③ 解析 HTML 后，继续请求 /app.js",
            frames=150,
        ),
        scene(
            "scene-4",
            "响应静态资源",
            "服务端返回 JS 文件，浏览器执行脚本、渲染页面。"
            "整个过程中每个请求都独立、无状态，靠 Cookie / Token 把状态带过去。",
            [
                packet(
                    "server", "client", "200 OK · JS", at=18,
                    length="38 KB", color="purple", dur=66,
                ),
                state("client", "FETCHING", "RENDERED", 84),
            ],
            "④ 返回 JS，浏览器执行并完成渲染",
            frames=150,
        ),
    ]

    return compile_props(
        "http.request",
        "HTTP 请求与响应",
        "打开一个网页，背后发生了几次往返？",
        actors,
        scenes,
    )

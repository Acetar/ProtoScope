"""知识点目录 + 规则库注册表。

目录里的一条 = 一个有"人写好剧本"的知识点；
用户自由描述时，先用别名/关键词在这里匹配，匹配不到才落到大模型。
"""
from __future__ import annotations

from typing import Callable

from .library import (
    arp_resolve,
    dns_resolve,
    http_request,
    tcp_handshake,
    tcp_teardown,
    tls_handshake,
)

Builder = Callable[[], dict]

# id -> 构造器
BUILDERS: dict[str, Builder] = {
    "tcp.handshake": tcp_handshake.build,
    "tcp.teardown": tcp_teardown.build,
    "tls.handshake": tls_handshake.build,
    "http.request": http_request.build,
    "arp.resolve": arp_resolve.build,
    "dns.resolve": dns_resolve.build,
}

# 展示用元数据；aliases 同时用于自由文本匹配
CATALOG: list[dict] = [
    {
        "id": "tcp.handshake",
        "title": "TCP 三次握手",
        "summary": "SYN / SYN+ACK / ACK，以及「为什么必须三次」。",
        "aliases": ["三次握手", "tcp握手", "建立连接", "syn", "three-way handshake", "handshake"],
        "actors": ["客户端", "服务端"],
    },
    {
        "id": "tcp.teardown",
        "title": "TCP 四次挥手",
        "summary": "FIN / ACK / FIN / ACK 与 TIME_WAIT 的由来。",
        "aliases": ["四次挥手", "断开连接", "关闭连接", "fin", "time_wait", "teardown"],
        "actors": ["主动关闭方", "被动关闭方"],
    },
    {
        "id": "tls.handshake",
        "title": "TLS 1.3 握手",
        "summary": "ClientHello / ServerHello + 证书 / 双端 Finished。",
        "aliases": ["tls", "https", "ssl", "加密握手", "证书", "clienthello"],
        "actors": ["浏览器", "HTTPS 服务器"],
    },
    {
        "id": "http.request",
        "title": "HTTP 请求与响应",
        "summary": "GET HTML、200 OK、再取静态资源的两轮往返。",
        "aliases": ["http", "请求响应", "网页加载", "get请求", "响应报文", "状态码"],
        "actors": ["浏览器", "Web 服务器"],
    },
    {
        "id": "arp.resolve",
        "title": "ARP 地址解析",
        "summary": "广播询问、单播应答、写入缓存后封装发送。",
        "aliases": ["arp", "mac地址", "地址解析", "局域网", "广播"],
        "actors": ["主机", "网关"],
    },
    {
        "id": "dns.resolve",
        "title": "DNS 递归解析",
        "summary": "递归查询、迭代询问根与权威、TTL 缓存命中。",
        "aliases": ["dns", "域名解析", "递归查询", "迭代查询", "ttl", "a记录"],
        "actors": ["客户端", "本地 DNS 服务器"],
    },
]


def by_id(kp_id: str) -> dict | None:
    return next((c for c in CATALOG if c["id"] == kp_id), None)


def summary() -> list[dict]:
    """给前端的目录列表，字段与 KnowledgePoint 模型一一对应。"""
    return [
        {
            "id": c["id"],
            "title": c["title"],
            "summary": c["summary"],
            "aliases": c["aliases"],
            "actors": c["actors"],
        }
        for c in CATALOG
    ]


def match_text(text: str) -> str | None:
    """在自由描述里找最先命中的别名，返回知识点 id。"""
    low = text.lower().replace(" ", "")
    best: tuple[int, str] | None = None
    for item in CATALOG:
        for alias in item["aliases"]:
            key = alias.lower().replace(" ", "")
            if key and key in low:
                pos = low.index(key)
                if best is None or pos < best[0]:
                    best = (pos, item["id"])
    return best[1] if best else None

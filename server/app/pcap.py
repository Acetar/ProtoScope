"""pcap 解析：把抓包文件转成"报文列表 + 会话 + 字段树"。

对应设计文档 4.1 的**最小实现**，明确不做的事：
- 不做 TCP 流重组（payload 只给可打印预览，够用即可）；
- 不做实时抓包，只吃上传的文件；
- 单文件上限 5000 包 / 12 MB，超出截断并置 truncated=True。

字段路径沿用 Wireshark 的写法（ip.src / tcp.flags.syn / http.request.method），
这样前端字段树、AI 引用 [P12] 与 tcp.flags.syn 用的是同一套命名，不需要翻译层。
"""

from __future__ import annotations

import io
import time
from typing import Any

MAX_PACKETS = 5000
MAX_BYTES = 12 * 1024 * 1024

# scapy 在 Windows 上会抱怨缺少 Npcap，解析文件用不到它，压掉噪音
import logging

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
logging.getLogger("scapy.loading").setLevel(logging.ERROR)


class CaptureError(ValueError):
    """解析失败时抛出，消息会直接展示给用户。"""


def _open_reader(data: bytes):
    # 必须先导入 L2/inet 层：scapy 靠这次导入把链路类型 1（Ethernet）注册进
    # conf.l2types。否则 PcapReader 会直接吐 Raw 包（"unknown LL type [1]"），
    # 后面所有 getlayer() 都拿不到东西。
    from scapy.layers.inet import ICMP, IP, TCP, UDP  # noqa: F401
    from scapy.layers.inet6 import IPv6  # noqa: F401
    from scapy.layers.l2 import ARP, Ether  # noqa: F401
    from scapy.utils import PcapNgReader, PcapReader

    magic = data[:4]
    if magic == b"\x0a\x0d\x0d\x0a":  # pcapng 的 Section Header Block
        return PcapNgReader(io.BytesIO(data))
    if magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        return PcapReader(io.BytesIO(data))
    raise CaptureError("不是 pcap/pcapng 文件。请在 Wireshark 里『另存为 / Save As』选择 pcap 或 pcapng 格式。")


def _ts_text(ts: float) -> str:
    whole = int(ts)
    us = int(round((ts - whole) * 1_000_000))
    if us >= 1_000_000:  # 0.009999999 这类浮点误差会凑到 1000000
        whole += 1
        us -= 1_000_000
    return time.strftime("%H:%M:%S", time.localtime(whole)) + ".%06d" % us


# scapy 的 flags 是单字母串（"SA"），不是 "SYN, ACK"
FLAG_BITS = [("syn", "S"), ("ack", "A"), ("fin", "F"), ("rst", "R"), ("psh", "P"), ("urg", "U")]


def _flags_text(tcp) -> str:
    """把 TCP 标志位拼成 SYN / SYN, ACK 这种可读串。"""
    raw = str(tcp.flags)
    return ", ".join(name.upper() for name, letter in FLAG_BITS if letter in raw)


def _printable(payload: bytes, limit: int = 64) -> str:
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in payload[:limit])
    return text


def _parse_one(pkt, index: int) -> dict[str, Any] | None:
    """把单个 scapy 包拆成记录；非 IP/ARP 的包返回 None（不展示链路层噪音）。"""
    from scapy.layers.inet import ICMP, IP, TCP, UDP
    from scapy.layers.inet6 import IPv6
    from scapy.layers.l2 import ARP, Ether
    from scapy.packet import Raw

    l3 = pkt.getlayer(IP) or pkt.getlayer(IPv6)
    arp = pkt.getlayer(ARP)
    if l3 is None and arp is None:
        return None

    fields: dict[str, str] = {}
    length = len(pkt)
    ts = float(pkt.time)

    eth = pkt.getlayer(Ether)
    if eth is not None:
        fields["eth.src"] = eth.src
        fields["eth.dst"] = eth.dst

    if arp is not None:
        fields.update(
            {
                "arp.op": "request" if arp.op == 1 else "reply",
                "arp.psrc": arp.psrc,
                "arp.pdst": arp.pdst,
            }
        )
        return {
            "index": index,
            "ts": ts,
            "time": _ts_text(ts),
            "src": arp.psrc,
            "dst": arp.pdst,
            "srcPort": None,
            "dstPort": None,
            "proto": "ARP",
            "length": length,
            "summary": f"ARP {fields['arp.op']}: 谁是 {arp.pdst}？" if arp.op == 1 else f"ARP reply: {arp.psrc} 在此",
            "flags": "",
            "payloadLen": 0,
            "fields": fields,
        }

    src, dst = l3.src, l3.dst
    version = l3.version if hasattr(l3, "version") else (6 if l3.__class__.__name__ == "IPv6" else 4)
    fields["ip.version"] = str(version)
    fields["ip.src"] = src
    fields["ip.dst"] = dst
    if version == 4:
        fields["ip.ttl"] = str(l3.ttl)
        fields["ip.proto"] = str(l3.proto)
    else:
        fields["ipv6.hlim"] = str(l3.hlim)

    tcp = pkt.getlayer(TCP)
    udp = pkt.getlayer(UDP)
    icmp = pkt.getlayer(ICMP)
    raw = pkt.getlayer(Raw)
    payload = bytes(raw.load) if raw is not None else b""

    proto = "OTHER"
    sport = dport = None
    flags = ""
    summary = ""

    if tcp is not None:
        proto = "TCP"
        sport, dport = tcp.sport, tcp.dport
        flags = _flags_text(tcp)
        fields.update(
            {
                "tcp.sport": str(tcp.sport),
                "tcp.dport": str(tcp.dport),
                "tcp.seq": str(tcp.seq),
                "tcp.ack": str(tcp.ack) if "A" in str(tcp.flags) else "",
                "tcp.flags": flags,
                "tcp.window": str(tcp.window),
                "tcp.len": str(len(payload)),
            }
        )
        for bit, letter in FLAG_BITS:
            fields[f"tcp.flags.{bit}"] = "1" if letter in str(tcp.flags) else "0"
        summary = f"{flags or 'TCP'} {sport} → {dport}"
    elif udp is not None:
        proto = "UDP"
        sport, dport = udp.sport, udp.dport
        fields.update({"udp.sport": str(udp.sport), "udp.dport": str(udp.dport), "udp.length": str(udp.len)})
        summary = f"UDP {sport} → {dport}"
    elif icmp is not None:
        proto = "ICMP"
        fields.update({"icmp.type": str(icmp.type), "icmp.code": str(icmp.code)})
        summary = f"ICMP type={icmp.type} code={icmp.code}"
    else:
        summary = f"IP proto={fields.get('ip.proto', '?')}"

    fields["frame.len"] = str(length)
    fields["frame.time"] = _ts_text(ts)

    # 应用层识别：只认最典型的几种，够演示"点开看请求行"
    if payload:
        head = _printable(payload, 120)
        fields["payload.len"] = str(len(payload))
        fields["payload.text"] = head
        if payload[:4] in (b"GET ", b"POST", b"HEAD", b"PUT "):
            parts = payload.split(b"\r\n")[0].decode("latin-1", "replace").split(" ")
            if len(parts) >= 2:
                fields["http.request.method"] = parts[0]
                fields["http.request.uri"] = parts[1]
                summary = f"HTTP {parts[0]} {parts[1]}"
        elif payload.startswith(b"HTTP/1."):
            first = payload.split(b"\r\n")[0].decode("latin-1", "replace")
            code = first.split(" ")[1] if len(first.split(" ")) > 1 else ""
            if code:
                fields["http.response.code"] = code
                summary = f"HTTP {code}"

    return {
        "index": index,
        "ts": ts,
        "time": _ts_text(ts),
        "src": src,
        "dst": dst,
        "srcPort": sport,
        "dstPort": dport,
        "proto": proto,
        "length": length,
        "summary": summary,
        "flags": flags,
        "payloadLen": len(payload),
        "fields": {k: v for k, v in fields.items() if v != ""},
    }


def _session_key(p: dict[str, Any]) -> tuple:
    if p["proto"] in ("TCP", "UDP") and p["srcPort"] is not None:
        a = (p["src"], p["srcPort"])
        b = (p["dst"], p["dstPort"])
        return (p["proto"],) + tuple(sorted([a, b]))
    return (p["proto"],) + tuple(sorted([p["src"], p["dst"]]))


def _label(records: list[dict[str, Any]]) -> str:
    """给会话起个中文名，答辩时列表里一眼能读懂。"""
    flags = " ".join(r["flags"] for r in records)
    proto = records[0]["proto"]
    dports = {r["dstPort"] for r in records if r["dstPort"]}
    if proto == "TCP":
        has_syn = "SYN" in flags
        has_synack = any("SYN" in r["flags"] and "ACK" in r["flags"] for r in records)
        has_fin = "FIN" in flags
        has_http = any("http.request" in " ".join(r["fields"]) for r in records) or any(
            "HTTP" in r["summary"] for r in records
        )
        if has_http:
            return "HTTP 请求 / 响应"
        if 443 in dports or 8443 in dports:
            base = "TLS 握手"
        elif 80 in dports:
            base = "HTTP 请求 / 响应"
        elif 22 in dports:
            base = "SSH 连接"
        else:
            base = "TCP 连接"
        if has_syn and has_synack and has_fin:
            return base + "（握手 + 挥手）"
        if has_syn and has_synack:
            return base + "（三次握手）"
        return base
    if proto == "UDP":
        if 53 in dports:
            return "DNS 查询 / 响应"
        return "UDP 会话"
    if proto == "ARP":
        return "ARP 地址解析"
    if proto == "ICMP":
        return "ICMP 探测"
    return f"{proto} 会话"


def parse_capture(data: bytes, filename: str = "") -> dict[str, Any]:
    """解析 pcap 字节流，返回可直接 JSON 序列化的结构。"""
    if not data:
        raise CaptureError("文件是空的。")
    if len(data) > MAX_BYTES:
        raise CaptureError(f"文件太大（{len(data) / 1024 / 1024:.1f} MB），请裁剪到 12 MB 以内。")

    reader = _open_reader(data)
    records: list[dict[str, Any]] = []
    truncated = False

    try:
        for i, pkt in enumerate(reader, start=1):
            if i > MAX_PACKETS:
                truncated = True
                break
            try:
                rec = _parse_one(pkt, i)
            except Exception:  # 单个坏包不该让整个文件失败
                continue
            if rec is not None:
                records.append(rec)
    except CaptureError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CaptureError(f"解析到一半失败了：{exc}") from exc
    finally:
        try:
            reader.close()
        except Exception:  # noqa: BLE001
            pass

    if not records:
        raise CaptureError("这个文件里没有可显示的 IP/ARP 报文，可能只抓到了链路层广播或格式不受支持。")

    # 按五元组分组成会话
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for rec in records:
        groups.setdefault(_session_key(rec), []).append(rec)

    sessions = []
    for idx, (key, group) in enumerate(sorted(groups.items(), key=lambda kv: kv[1][0]["ts"]), start=1):
        sid = f"s{idx}"
        first = group[0]
        # 客户端 = 先发包的一方；TCP 里更准确是发 SYN 的一方
        client, server = first["src"], first["dst"]
        for rec in group:
            if "SYN" in rec["flags"] and "ACK" not in rec["flags"]:
                client, server = rec["src"], rec["dst"]
                break
        for rec in group:
            rec["sessionId"] = sid
        sessions.append(
            {
                "id": sid,
                "proto": first["proto"],
                "client": client,
                "server": server,
                "clientPort": first["srcPort"] if first["src"] == client else first["dstPort"],
                "serverPort": first["dstPort"] if first["src"] == client else first["srcPort"],
                "label": _label(group),
                "packetCount": len(group),
                "startTs": first["ts"],
                "endTs": group[-1]["ts"],
                "durationMs": round((group[-1]["ts"] - first["ts"]) * 1000),
                "packetIndexes": [r["index"] for r in group],
            }
        )

    return {
        "filename": filename,
        "size": len(data),
        "packetCount": len(records),
        "sessionCount": len(sessions),
        "truncated": truncated,
        "sessions": sessions,
        "packets": records,
    }

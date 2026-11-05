"""生成一份演示用 pcap：ARP 解析 → TCP 三次握手 → HTTP 请求/响应 → 四次挥手。

跑法：python tools/make_sample_pcap.py
产物：samples/http-handshake.pcap（几 KB，随源码一起交付）
"""

from __future__ import annotations

import pathlib
import time

from scapy.all import ARP, Ether, IP, TCP, Raw, wrpcap

CLIENT_IP, CLIENT_MAC, CLIENT_PORT = "10.0.0.5", "aa:bb:cc:00:11:22", 51234
SERVER_IP, SERVER_MAC, SERVER_PORT = "93.184.216.34", "00:1c:42:00:00:09", 80
GATEWAY_IP = "10.0.0.1"


def build() -> list:
    t0 = float(int(time.time()) - 3600)
    pkts = []
    seq_c, seq_s = 1000, 5000

    def at(offset: float):
        return t0 + offset

    # 1-2 ARP：客户端问网关的 MAC
    arp_req = Ether(dst="ff:ff:ff:ff:ff:ff", src=CLIENT_MAC) / ARP(
        op=1, psrc=CLIENT_IP, pdst=GATEWAY_IP
    )
    arp_req.time = at(0.0)
    pkts.append(arp_req)

    arp_rep = Ether(dst=CLIENT_MAC, src="00:1c:42:00:00:01") / ARP(
        op=2, psrc=GATEWAY_IP, pdst=CLIENT_IP
    )
    arp_rep.time = at(0.002)
    pkts.append(arp_rep)

    # 3 三次握手 SYN
    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="S", seq=seq_c, window=64240
    )
    p.time = at(0.010)
    pkts.append(p)

    # 4 SYN + ACK
    p = Ether(dst=CLIENT_MAC, src=SERVER_MAC) / IP(src=SERVER_IP, dst=CLIENT_IP, ttl=57) / TCP(
        sport=SERVER_PORT, dport=CLIENT_PORT, flags="SA", seq=seq_s, ack=seq_c + 1, window=65535
    )
    p.time = at(0.032)
    pkts.append(p)

    # 5 ACK
    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="A", seq=seq_c + 1, ack=seq_s + 1, window=64240
    )
    p.time = at(0.033)
    pkts.append(p)

    # 6 HTTP GET
    req = (
        f"GET /index.html HTTP/1.1\r\nHost: {SERVER_IP}\r\n"
        "User-Agent: ProtocolMotion/1.0\r\nAccept: text/html\r\n\r\n"
    ).encode()
    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="PA", seq=seq_c + 1, ack=seq_s + 1, window=64240
    ) / Raw(load=req)
    p.time = at(0.040)
    pkts.append(p)

    # 7 200 OK
    body = "<html><body><h1>It works</h1></body></html>"
    resp = (
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
        f"Content-Length: {len(body)}\r\nServer: demo\r\n\r\n{body}"
    ).encode()
    p = Ether(dst=CLIENT_MAC, src=SERVER_MAC) / IP(src=SERVER_IP, dst=CLIENT_IP, ttl=57) / TCP(
        sport=SERVER_PORT, dport=CLIENT_PORT, flags="PA", seq=seq_s + 1, ack=seq_c + 1 + len(req), window=65535
    ) / Raw(load=resp)
    p.time = at(0.071)
    pkts.append(p)

    # 8 ACK（确认响应）
    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="A", seq=seq_c + 1 + len(req), ack=seq_s + 1 + len(resp), window=64240
    )
    p.time = at(0.072)
    pkts.append(p)

    # 9-12 四次挥手
    fin_seq = seq_c + 1 + len(req)
    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="FA", seq=fin_seq, ack=seq_s + 1 + len(resp), window=64240
    )
    p.time = at(0.210)
    pkts.append(p)

    ack_seq_s = seq_s + 1 + len(resp)
    p = Ether(dst=CLIENT_MAC, src=SERVER_MAC) / IP(src=SERVER_IP, dst=CLIENT_IP, ttl=57) / TCP(
        sport=SERVER_PORT, dport=CLIENT_PORT, flags="A", seq=ack_seq_s, ack=fin_seq + 1, window=65535
    )
    p.time = at(0.229)
    pkts.append(p)

    p = Ether(dst=CLIENT_MAC, src=SERVER_MAC) / IP(src=SERVER_IP, dst=CLIENT_IP, ttl=57) / TCP(
        sport=SERVER_PORT, dport=CLIENT_PORT, flags="FA", seq=ack_seq_s, ack=fin_seq + 1, window=65535
    )
    p.time = at(0.230)
    pkts.append(p)

    p = Ether(dst=SERVER_MAC, src=CLIENT_MAC) / IP(src=CLIENT_IP, dst=SERVER_IP, ttl=64) / TCP(
        sport=CLIENT_PORT, dport=SERVER_PORT, flags="A", seq=fin_seq + 1, ack=ack_seq_s + 1, window=64240
    )
    p.time = at(0.231)
    pkts.append(p)

    return pkts


if __name__ == "__main__":
    out = pathlib.Path("samples/http-handshake.pcap")
    out.parent.mkdir(parents=True, exist_ok=True)
    packets = build()
    wrpcap(str(out), packets)
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(packets)} packets)")

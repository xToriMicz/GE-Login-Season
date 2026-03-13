#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ทดสอบ proxy list — เช็คว่าตัวไหนใช้ได้จริง + เป็น IP ไทย
รัน: python test_proxies.py
      python test_proxies.py --fetch     ดึง proxy ใหม่จาก API ก่อนทดสอบ
      python test_proxies.py --all       ทดสอบทั้งไทยและต่างประเทศ
ผลลัพธ์: สร้างไฟล์ proxies.txt เฉพาะตัวที่ผ่านทดสอบ
"""

import socket
import urllib.request
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# แหล่ง API ที่ดึง proxy ได้อัตโนมัติ
PROXY_APIS = [
    # ProxyScrape — TH HTTP
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=TH",
    # ProxyScrape — TH SOCKS4
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=TH",
    # ProxyScrape — TH SOCKS5
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=TH",
    # ProxyScrape — All TH
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=all&timeout=5000&country=TH",
]

# Hardcoded candidates (known Thai IPs — fallback ถ้า API ดึงไม่ได้)
HARDCODED = [
    "http://203.146.80.102:8080",
    "http://61.91.162.126:8080",
    "http://183.88.231.188:34599",
    "http://49.48.66.40:8080",
    "http://182.53.202.208:8080",
    "http://124.121.2.247:8080",
    "http://118.175.30.26:80",
    "http://61.19.145.66:8080",
    "http://159.192.102.249:8080",
    "http://113.53.61.101:8080",
    "http://202.129.206.239:3129",
    "http://202.129.206.239:3128",
    "http://203.223.89.185:8080",
    "http://171.103.240.54:80",
    "http://118.174.175.86:8080",
    "http://101.109.122.189:8080",
    "http://163.44.197.212:54729",
    "http://49.49.63.2:8080",
    "http://110.171.40.132:8080",
    "http://182.52.229.165:8080",
    "http://202.183.236.220:8080",
    "http://182.53.143.200:8080",
    "http://27.131.146.251:8080",
    "http://124.122.115.165:8080",
    "http://110.49.53.69:8080",
    "http://124.121.2.241:8080",
    "http://1.0.170.50:8080",
    "http://183.88.214.44:8080",
    "http://58.137.174.101:8080",
    "http://110.164.128.124:8080",
    "http://118.172.184.25:8080",
    "http://203.150.172.151:8080",
    "http://203.150.128.104:8080",
    "http://1.20.184.214:8080",
    "http://183.88.214.84:8080",
    "http://180.180.218.250:8080",
]


def fetch_proxies_from_apis() -> list[str]:
    """ดึง proxy จาก API แล้วรวมกับ hardcoded"""
    fetched = set()
    for api_url in PROXY_APIS:
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            text = resp.read().decode("utf-8", errors="ignore")
            for line in text.strip().splitlines():
                line = line.strip()
                if line and ":" in line:
                    # Normalize: add http:// if no scheme
                    if "://" not in line:
                        line = "http://" + line
                    fetched.add(line)
            print(f"  API: {len(fetched)} proxies from {api_url.split('?')[0]}...")
        except Exception as e:
            print(f"  API FAIL: {api_url.split('?')[0]} ({str(e)[:40]})")
    return list(fetched)


def test_proxy(proxy_url: str, timeout: int = 8) -> dict:
    """ทดสอบ proxy 1 ตัว — เช็ค connectivity + ตรวจว่า IP เป็นไทย"""
    result = {"proxy": proxy_url, "ok": False, "ip": None, "country": None, "latency_ms": None}

    # Parse host:port
    clean = proxy_url.replace("http://", "").replace("socks5://", "")
    if "@" in clean:
        clean = clean.split("@", 1)[1]
    host, port_str = clean.rsplit(":", 1)
    port = int(port_str)

    # Step 1: TCP connect test
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
    except Exception:
        return result

    # Step 2: HTTP request through proxy
    try:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(proxy_handler)

        start = time.time()
        req = urllib.request.Request("http://ip-api.com/json/?fields=query,country,countryCode", headers={"User-Agent": "Mozilla/5.0"})
        resp = opener.open(req, timeout=timeout)
        elapsed = (time.time() - start) * 1000

        data = json.loads(resp.read().decode())
        result["ip"] = data.get("query")
        result["country"] = data.get("countryCode", "??")
        result["latency_ms"] = int(elapsed)
        result["ok"] = True
    except Exception:
        pass

    return result


def main():
    do_fetch = "--fetch" in sys.argv or "-f" in sys.argv
    want_all = "--all" in sys.argv

    if do_fetch:
        print("Fetching fresh proxies from APIs...")
        api_proxies = fetch_proxies_from_apis()
        # รวมกับ hardcoded (deduplicate)
        seen = set()
        CANDIDATES = []
        for p in api_proxies + HARDCODED:
            key = p.replace("http://", "").replace("socks5://", "").replace("socks4://", "")
            if key not in seen:
                seen.add(key)
                CANDIDATES.append(p)
        print(f"Total unique candidates: {len(CANDIDATES)}")
    else:
        CANDIDATES = list(HARDCODED)
        print("Using hardcoded list. Use --fetch to pull fresh proxies from APIs.")

    print(f"\nTesting {len(CANDIDATES)} proxy candidates...")
    print("=" * 70)

    working = []
    thai_working = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(test_proxy, p): p for p in CANDIDATES}
        for i, future in enumerate(as_completed(futures), 1):
            r = future.result()
            proxy_short = r["proxy"].replace("http://", "")
            if r["ok"]:
                flag = "TH" if r["country"] == "TH" else r["country"]
                icon = "+" if r["country"] == "TH" else "~"
                print(f"  [{icon}] {proxy_short:30s} -> {r['ip']:16s} {flag:4s} {r['latency_ms']:5d}ms")
                working.append(r)
                if r["country"] == "TH":
                    thai_working.append(r)
            else:
                print(f"  [x] {proxy_short:30s} -> DEAD")

    print("=" * 70)
    print(f"Results: {len(working)} working / {len(CANDIDATES)} total")
    print(f"Thai IP: {len(thai_working)} proxies")

    # เรียงตาม latency
    thai_working.sort(key=lambda x: x["latency_ms"])

    if thai_working:
        # เขียนเฉพาะ Thai proxy ที่ใช้ได้
        with open("proxies.txt", "w", encoding="utf-8") as f:
            f.write("# Thai Free Proxies — auto-tested " + time.strftime("%Y-%m-%d %H:%M") + "\n")
            f.write(f"# {len(thai_working)} working Thai proxies\n")
            for r in thai_working:
                f.write(f"{r['proxy'].replace('http://', '')}\n")
        print(f"\nSaved {len(thai_working)} Thai proxies to proxies.txt")
        print("Top 5 fastest:")
        for r in thai_working[:5]:
            print(f"  {r['proxy'].replace('http://', ''):30s} {r['latency_ms']}ms")
    elif working:
        # ถ้าไม่มี Thai ก็เขียนทุกตัวที่ใช้ได้
        working.sort(key=lambda x: x["latency_ms"])
        with open("proxies.txt", "w", encoding="utf-8") as f:
            f.write("# Free Proxies (non-Thai) — auto-tested " + time.strftime("%Y-%m-%d %H:%M") + "\n")
            for r in working:
                f.write(f"# {r['country']} {r['latency_ms']}ms\n")
                f.write(f"{r['proxy'].replace('http://', '')}\n")
        print(f"\nNo Thai proxies found. Saved {len(working)} non-Thai proxies to proxies.txt")
    else:
        print("\nNo working proxies found at all. Try again later or use a different source.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

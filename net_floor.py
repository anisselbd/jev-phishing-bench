"""Measure the network round-trip floor to each API host, to separate network time from inference time.

Two floors per host. "cold": each probe opens a fresh HTTPS connection (DNS + TCP + TLS + one tiny GET).
"warm": probes reuse one keep-alive connection, which is what the benchmark runners do, so the warm p50 is
the smallest latency any API call from this machine could show. Written to results/net_floor.json.

Usage: uv run net_floor.py [--n 20]
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from bench.common import RESULTS_DIR, env


def summarize(samples: list[float]) -> dict:
    samples = sorted(samples)
    n = len(samples)
    return {"p50_s": statistics.median(samples), "min_s": samples[0], "p95_s": samples[int(0.95 * (n - 1))]}


def probe(url: str, n: int) -> dict:
    cold, warm = [], []
    status = None
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.get(url)
                status = resp.status_code
        except httpx.HTTPError as exc:
            status = f"error: {type(exc).__name__}"
        cold.append(time.perf_counter() - t0)
    with httpx.Client(timeout=20) as client:
        client.get(url)  # open the connection once
        for _ in range(n):
            t0 = time.perf_counter()
            try:
                client.get(url)
            except httpx.HTTPError:
                pass
            warm.append(time.perf_counter() - t0)
    return {"url": url, "n": n, "last_status": status, "cold": summarize(cold), "warm": summarize(warm)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()

    typesafe = env("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
    llm = env("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    llm_host = f"{urlparse(llm).scheme}://{urlparse(llm).netloc}/"

    out = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "machine": platform.platform(),
        "note": "cold = fresh connection per probe (DNS + TCP + TLS + one tiny GET); warm = reused keep-alive connection, as the runners do",
        "hosts": {},
    }
    for name, url in (("typesafe", typesafe + "/"), ("llm", llm_host)):
        print(f"probing {url} x{args.n}")
        out["hosts"][name] = probe(url, args.n)
        r = out["hosts"][name]
        for kind in ("cold", "warm"):
            k = r[kind]
            print(f"  {kind}: p50 {k['p50_s']*1000:.0f} ms, min {k['min_s']*1000:.0f} ms, p95 {k['p95_s']*1000:.0f} ms (status {r['last_status']})")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "net_floor.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {RESULTS_DIR / 'net_floor.json'}")


if __name__ == "__main__":
    main()

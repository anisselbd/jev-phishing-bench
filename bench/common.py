"""Paths, environment, JSONL helpers, resumable runs and retry logic shared by every script."""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
RAW_DIR = RESULTS_DIR / "raw"
EMAILS_FILE = DATA_DIR / "emails.jsonl"

SEED = 20260916

load_dotenv(ROOT / ".env")


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing {name}. Put it in .env (see .env.example).")
    return value if value is not None else ""


def env_float(name: str, default: float | None = None) -> float | None:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    return float(raw)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def load_emails() -> list[dict[str, Any]]:
    if not EMAILS_FILE.exists():
        sys.exit(f"{EMAILS_FILE} not found. Run prepare_data.py first.")
    return read_jsonl(EMAILS_FILE)


def done_ids(path: Path) -> set[str]:
    """IDs already present in a run file, so a rerun never bills an email twice."""
    return {r["id"] for r in read_jsonl(path) if r.get("ok")}


def select_emails(
    emails: list[dict[str, Any]],
    limit: int | None = None,
    sample: int | None = None,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """Fixed-order subset: `sample` picks a seeded random subset, `limit` truncates."""
    chosen = list(emails)
    if sample:
        rng = random.Random(seed)
        chosen = rng.sample(chosen, min(sample, len(chosen)))
        chosen.sort(key=lambda e: e["order"])
    if limit:
        chosen = chosen[:limit]
    return chosen


class RateLimiter:
    """Simple requests-per-minute pacer for free-tier endpoints. rpm=0 disables it."""

    def __init__(self, rpm: float):
        self.interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self.last = 0.0

    def wait(self) -> None:
        if not self.interval:
            return
        now = time.monotonic()
        delay = self.last + self.interval - now
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


RETRY_STATUSES = {408, 429, 500, 502, 503, 504, 529}


def post_with_retry(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    max_attempts: int = 8,
    base_delay: float = 1.0,
    max_delay: float = 90.0,
    log: Callable[[str], None] = print,
) -> tuple[httpx.Response | None, float, int, str | None]:
    """POST with exponential backoff on 429/529/5xx and network errors.

    Returns (response, latency_seconds_of_the_successful_attempt, attempts, error).
    Latency covers only the final attempt, so retries never inflate the measurement.
    """
    error: str | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        try:
            resp = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            latency = time.perf_counter() - t0
            error = f"network: {type(exc).__name__}: {exc}"
            resp = None
        else:
            latency = time.perf_counter() - t0
            if resp.status_code < 400:
                return resp, latency, attempt, None
            error = f"http {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in RETRY_STATUSES:
                return resp, latency, attempt, error
        delay = min(max_delay, base_delay * (2 ** (attempt - 1))) * (0.5 + random.random())
        if resp is not None and resp.headers.get("retry-after"):
            try:
                delay = max(delay, float(resp.headers["retry-after"]))
            except ValueError:
                pass
        log(f"  retry {attempt}/{max_attempts} in {delay:.1f}s ({error[:120]})")
        time.sleep(delay)
    return None, 0.0, max_attempts, error


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a proportion. Returns (p, low, high)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return p, centre - half, centre + half


def pct(x: float, digits: int = 1) -> str:
    return "n/a" if x != x else f"{100 * x:.{digits}f}%"


def chunks(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

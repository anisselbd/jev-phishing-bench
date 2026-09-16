"""Download PhishNChips v5.2, verify checksums, and write data/emails.jsonl in a seeded fixed order.

Usage: uv run prepare_data.py [--force]
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import sys

import httpx

from bench.common import DATA_DIR, EMAILS_FILE, SEED, append_jsonl, sha256_file

HF_BASE = "https://huggingface.co/datasets/AreLit/PhishNChips/resolve/main/"

# SHA-256 values published in V5.2_RELEASE_MANIFEST.md of the dataset (generated 2026-04-08).
FILES = {
    "core_emails.csv": "cebb407ff8630491a97400e37464b8db8dfc4299164fca51fcb4ac7eec8204ef",
    "prompt_strategies.json": "0a293bb8e722d0621845f3e0f9b5cd8bd100818c35222c1cd6964a8fa3b367b0",
    "reference_results.csv": "5e15d7498aeadd73a23aec0b01979cacf02d172b97c88b3db0078609cc92ef15",
    "SOURCE_LICENSES.md": "129e19acd6ae8fb243b7861fd7f7c3c63987f431b0f73626b7d21206e275f8b7",
}

EMAIL_FIELDS = ["sender", "from", "subject", "body", "link_display_text", "link_url"]


def download(name: str, force: bool) -> None:
    target = DATA_DIR / "phishnchips" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force and sha256_file(target) == FILES[name]:
        print(f"  {name}: cached, checksum ok")
        return
    print(f"  {name}: downloading")
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        with client.stream("GET", HF_BASE + name) as resp:
            resp.raise_for_status()
            with target.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    digest = sha256_file(target)
    if digest != FILES[name]:
        sys.exit(f"Checksum mismatch for {name}: {digest} (expected {FILES[name]}). Dataset changed upstream.")
    print(f"  {name}: checksum ok")


def build_emails() -> None:
    src = DATA_DIR / "phishnchips" / "core_emails.csv"
    csv.field_size_limit(1 << 30)
    with src.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 2000:
        sys.exit(f"Expected 2000 rows, got {len(rows)}")

    records = []
    bad = 0
    for row in rows:
        try:
            email = json.loads(row["email_content"])
        except json.JSONDecodeError:
            bad += 1
            continue
        missing = [k for k in EMAIL_FIELDS if k not in email]
        if missing:
            bad += 1
            continue
        label = int(row["phish_label"])
        records.append(
            {
                "id": row["id"],
                "y": label,
                "label": "phishing" if label == 1 else "legitimate",
                "email": {k: email[k] for k in EMAIL_FIELDS},
                "email_raw": row["email_content"],
                "url_raw": row["url_raw"],
                "url_category": row["url_category"],
                "datasource": row["datasource"],
                "strategy": row["strategy"],
            }
        )
    if bad:
        print(f"  warning: {bad} rows skipped (unparseable email_content)")

    rng = random.Random(SEED)
    rng.shuffle(records)
    for i, r in enumerate(records):
        r["order"] = i

    if EMAILS_FILE.exists():
        EMAILS_FILE.unlink()
    for r in records:
        append_jsonl(EMAILS_FILE, r)

    counts = collections.Counter(r["label"] for r in records)
    lengths = sorted(len(r["email_raw"]) for r in records)
    print(f"  wrote {len(records)} emails to {EMAILS_FILE}")
    print(f"  labels: {dict(counts)}")
    print(f"  email_content chars: median {lengths[len(lengths)//2]}, p95 {lengths[int(0.95*len(lengths))]}, max {lengths[-1]}")
    print(f"  url categories: {dict(collections.Counter(r['url_category'] for r in records))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    args = parser.parse_args()

    print("Downloading PhishNChips v5.2 files")
    for name in FILES:
        download(name, args.force)
    print("Building emails.jsonl")
    build_emails()


if __name__ == "__main__":
    main()

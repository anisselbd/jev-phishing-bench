"""Run Jev (TypeSafe System One API) over the benchmark emails, one HTTP request per email.

Every request carries the same question set: a verdict Choice, a mirror Noul, five signal Nouls and two
alternative verdict wordings. Calls are sequential so latency is measured without contention. Output is
appended to results/raw/jev_pass<N>.jsonl and the run is resumable: emails already answered are skipped.

Usage:
  uv run run_jev.py --limit 10            # smoke test, prints raw answers
  uv run run_jev.py                       # full pass 1
  uv run run_jev.py --pass 2              # full pass 2 (stability)
  uv run run_jev.py --pass 3 --sample 200 # 200-email seeded subset (stability, next day)
  uv run run_jev.py --dry-run --limit 1   # print the request payload without calling the API
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import httpx

from bench.common import RAW_DIR, done_ids, env, append_jsonl, load_emails, post_with_retry, select_emails

# Task framing mirrors the "balanced" system prompt of the PhishNChips authors: an email assistant deciding
# whether the link is safe to click or a phishing attempt. No examples, no hints, no signal names.
QUESTIONS = {
    "verdict": {
        "type": "choice",
        "instructions": (
            "This email arrived in the user's inbox and contains a link (`link_url`). "
            "Is it a phishing attempt, or a legitimate message whose link is safe to click?"
        ),
        "criteria": {
            "phishing": "The email or its link is a phishing attempt or otherwise malicious. The user should not click the link.",
            "legitimate": "A normal, legitimate message. The link is safe to click.",
        },
    },
    "is_phishing": {
        "type": "noul",
        "instructions": "This email is a phishing attempt and the user should not click the link in `link_url`.",
        "criteria": {
            "true": "The email or its link is a phishing attempt or otherwise malicious.",
            "false": "The email is a normal, legitimate message and the link is safe to click.",
        },
    },
    # Five signals matching the URL-evasion taxonomy of the dataset.
    "sig_domain_mismatch": {
        "type": "noul",
        "instructions": (
            "The domain of the sender address in `from` is different from the organization or domain "
            "that the link in `link_url` points to."
        ),
    },
    "sig_free_hosting": {
        "type": "noul",
        "instructions": (
            "The link in `link_url` points to a URL shortener or to a free hosting or file-sharing platform "
            "(for example bit.ly, an IPFS gateway, Firebase, GitHub Pages, Google Docs) rather than to the "
            "organization's own website."
        ),
    },
    "sig_lure": {
        "type": "noul",
        "instructions": "The email asks the user to sign in, verify an account, or open a document or file through the link.",
    },
    "sig_urgency": {
        "type": "noul",
        "instructions": "The email pressures the user to act quickly, mentions a deadline, or threatens a consequence.",
    },
    "sig_generic_sender": {
        "type": "noul",
        "instructions": (
            "The sender uses a generic webmail address (such as gmail, outlook, yahoo, hotmail) in `from` "
            "while presenting themselves as a company, team, department or organization."
        ),
    },
    # Alternative wordings of the verdict, to measure Jev's own sensitivity to phrasing.
    "verdict_alt_click": {
        "type": "choice",
        "instructions": "Should the user click the link in this email?",
        "criteria": {
            "do_not_click": "No. The link may be phishing or malicious.",
            "click": "Yes. The email and its link look legitimate.",
        },
    },
    "verdict_alt_minimal": {
        "type": "choice",
        "instructions": "Classify this email.",
        "criteria": {"phishing": None, "legitimate": None},
    },
}


def build_payload(email: dict, model: str) -> dict:
    return {"state": email["email"], "model": model, "questions": QUESTIONS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pass", dest="pass_no", type=int, default=1, help="pass number (1 = main run)")
    parser.add_argument("--limit", type=int, help="stop after N emails")
    parser.add_argument("--sample", type=int, help="seeded random subset of N emails")
    parser.add_argument("--dry-run", action="store_true", help="print payload, do not call the API")
    args = parser.parse_args()

    model = env("TYPESAFE_MODEL", "jev-latest")
    base_url = env("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
    emails = select_emails(load_emails(), limit=args.limit, sample=args.sample)

    if args.dry_run:
        print(json.dumps(build_payload(emails[0], model), indent=2, ensure_ascii=False))
        return

    api_key = env("TYPESAFE_API_KEY", required=True)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url}/v1/systemone"
    out = RAW_DIR / f"jev_pass{args.pass_no}.jsonl"
    already = done_ids(out)
    todo = [e for e in emails if e["id"] not in already]
    print(f"pass {args.pass_no}: {len(todo)} emails to run ({len(already)} already done) -> {out}")

    started = time.monotonic()
    ok = errors = 0
    tokens_in = 0
    with httpx.Client(timeout=60) as client:
        for i, email in enumerate(todo, 1):
            payload = build_payload(email, model)
            resp, latency, attempts, error = post_with_retry(client, url, headers=headers, payload=payload)
            record = {
                "id": email["id"],
                "y": email["y"],
                "pass": args.pass_no,
                "ts": datetime.now(timezone.utc).isoformat(),
                "latency_s": latency,
                "attempts": attempts,
                "ok": False,
            }
            if resp is None or error:
                record["error"] = error or "unknown"
                errors += 1
            else:
                try:
                    body = resp.json()
                    record["model"] = body.get("model")
                    record["answers"] = body["answers"]
                    record["usage"] = body.get("usage", {})
                    record["ok"] = True
                    ok += 1
                    tokens_in += int(record["usage"].get("input_tokens", 0))
                except (ValueError, KeyError) as exc:
                    record["error"] = f"bad response: {exc}: {resp.text[:300]}"
                    errors += 1
            append_jsonl(out, record)

            if args.limit and args.limit <= 20 and record["ok"]:
                v = record["answers"]["verdict"]
                print(
                    f"{email['id']} y={email['y']} -> {v['choice']} p={v['probabilities']} conf={v['confidence']:.3f} "
                    f"noul={record['answers']['is_phishing']['noul']:.3f} {latency*1000:.0f} ms usage={record['usage']}"
                )
            elif i % 50 == 0 or i == len(todo):
                elapsed = time.monotonic() - started
                print(f"  {i}/{len(todo)} ok={ok} errors={errors} tokens_in={tokens_in} elapsed={elapsed:.0f}s")

    cost = tokens_in / 1e6 * 0.042
    print(f"done: ok={ok} errors={errors} input tokens={tokens_in} (list price ~${cost:.4f})")
    if errors and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

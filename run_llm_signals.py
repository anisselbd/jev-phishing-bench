"""Control 3: ask the LLM baseline the same five signal questions as Jev, in one JSON call per email.

The five questions are imported from run_jev.py so the wording is identical. The model returns one probability per
signal. Output: results/raw/llm_<model>_signals_pass<N>.jsonl, with latency, tokens and format errors, so the
decomposition can be compared at equal footing (same rule, same regression, same split).

Usage:
  uv run run_llm_signals.py --limit 5
  uv run run_llm_signals.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import httpx

from bench.common import RAW_DIR, RateLimiter, append_jsonl, done_ids, env, env_float, load_emails, post_with_retry, select_emails
from run_jev import QUESTIONS
from run_llm import JSON_RE, extract

SIGNALS = ["sig_domain_mismatch", "sig_free_hosting", "sig_lure", "sig_urgency", "sig_generic_sender"]

SYSTEM = (
    "You are an email security analyst. You will receive an email as a JSON object with the fields `sender`, `from`, "
    "`subject`, `body`, `link_display_text` and `link_url`. For each of the numbered statements below, give the "
    "probability (a number between 0 and 1) that the statement is true for this email. "
    "Answer with a single JSON object and nothing else, with exactly these keys: "
    + ", ".join(f'"{s}"' for s in SIGNALS)
    + ".\n\n"
    + "\n".join(f"{k + 1}. {s}: {QUESTIONS[s]['instructions']}" for k, s in enumerate(SIGNALS))
)
USER = "Email:\n\n{email}\n\nReply with JSON only: {{" + ", ".join(f'"{s}": 0 to 1' for s in SIGNALS) + "}}"


def parse_signals(text: str) -> tuple[dict | None, str | None]:
    if text is None:
        return None, "empty response"
    import re

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        m = JSON_RE.search(cleaned)
        if not m:
            return None, "no json object"
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None, "invalid json"
    if not isinstance(obj, dict):
        return None, "json is not an object"
    out = {}
    for s in SIGNALS:
        try:
            v = float(obj[s])
        except (KeyError, TypeError, ValueError):
            return None, f"missing or non-numeric {s}"
        if not 0.0 <= v <= 1.0:
            return None, f"{s} out of range"
        out[s] = v
    return out, None


def build_body(email: dict, model: str, provider: str, extra: dict) -> dict:
    user = USER.replace("{email}", email["email_raw"])
    if provider == "anthropic":
        body = {"model": model, "max_tokens": 256, "temperature": 0, "system": SYSTEM, "messages": [{"role": "user", "content": user}]}
    else:
        body = {
            "model": model,
            "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
    body.update(extra)
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pass", dest="pass_no", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    provider = env("LLM_PROVIDER", "openai").lower()
    base_url = env("LLM_BASE_URL", required=True).rstrip("/")
    model = env("LLM_MODEL", required=True)
    extra = json.loads(env("LLM_EXTRA_BODY", "{}") or "{}")
    emails = select_emails(load_emails(), limit=args.limit, sample=args.sample)
    if args.dry_run:
        print(json.dumps(build_body(emails[0], model, provider, extra), indent=2, ensure_ascii=False))
        return

    api_key = env("LLM_API_KEY") or (env("ANTHROPIC_API_KEY") if provider == "anthropic" else "")
    if not api_key:
        sys.exit("Missing LLM_API_KEY (or ANTHROPIC_API_KEY) in .env.")
    price_in, price_out = env_float("LLM_PRICE_IN", 0.0), env_float("LLM_PRICE_OUT", 0.0)
    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        url = f"{base_url}/v1/messages"
    else:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/chat/completions"

    out = RAW_DIR / f"llm_{model}_signals_pass{args.pass_no}.jsonl"
    already = done_ids(out)
    todo = [e for e in emails if e["id"] not in already]
    limiter = RateLimiter(env_float("LLM_RPM", 0.0) or 0.0)
    print(f"{model} signals pass {args.pass_no}: {len(todo)} emails to run ({len(already)} done) -> {out}", flush=True)

    started = time.monotonic()
    ok = api_errors = format_errors = 0
    tok_in = tok_out = 0
    failures = 0
    with httpx.Client(timeout=120) as client:
        for i, email in enumerate(todo, 1):
            limiter.wait()
            body = build_body(email, model, provider, extra)
            resp, latency, attempts, error = post_with_retry(client, url, headers=headers, payload=body, log=lambda _m: None)
            record = {
                "id": email["id"], "y": email["y"], "pass": args.pass_no, "model": model, "provider": provider,
                "ts": datetime.now(timezone.utc).isoformat(), "latency_s": latency, "attempts": attempts, "ok": False,
            }
            if resp is None or error:
                record["error"] = error or "unknown"
                api_errors += 1
                failures += 1
            else:
                failures = 0
                try:
                    data = resp.json()
                    text, usage = extract(data, provider)
                    record["raw"] = text
                    record["usage"] = usage
                    record["usage_raw"] = data.get("usage", {})
                    parsed, fmt_err = parse_signals(text)
                    record["ok"] = True
                    ok += 1
                    tok_in += int(usage["input_tokens"] or 0)
                    tok_out += int(usage["output_tokens"] or 0)
                    if parsed:
                        record["signals"] = parsed
                    else:
                        record["format_error"] = fmt_err
                        format_errors += 1
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    record["error"] = f"bad response: {exc}: {resp.text[:300]}"
                    api_errors += 1
            append_jsonl(out, record)
            if args.limit and args.limit <= 20 and record["ok"]:
                print(f"{email['id']} y={email['y']} -> {record.get('signals') or record.get('format_error')} {latency*1000:.0f} ms {record['usage']}", flush=True)
            elif i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} ok={ok} api_errors={api_errors} format_errors={format_errors} elapsed={time.monotonic()-started:.0f}s", flush=True)
            if failures >= 5:
                print("5 consecutive failures, stopping; rerun to resume.", flush=True)
                break
    cost = tok_in / 1e6 * price_in + tok_out / 1e6 * price_out
    print(f"done: ok={ok} api_errors={api_errors} format_errors={format_errors} tokens in/out={tok_in}/{tok_out} list cost ~${cost:.4f}", flush=True)


if __name__ == "__main__":
    main()

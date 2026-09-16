"""Run the LLM baseline over the benchmark emails through any OpenAI-compatible chat/completions endpoint.

The system prompt is the "balanced" strategy of the PhishNChips authors, loaded verbatim from the dataset's
prompt_strategies.json. Only the answer-format sentence is replaced so the model returns JSON with a verdict
and a verbalized phishing probability. Calls are sequential, paced by LLM_RPM, resumable, and appended to
results/raw/llm_pass<N>.jsonl.

Environment (.env): LLM_PROVIDER (openai | anthropic), LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_PRICE_IN,
LLM_PRICE_OUT, LLM_RPM, optional LLM_EXTRA_BODY (JSON merged into the request body, e.g. Gemini thinking settings).
With LLM_PROVIDER=anthropic the runner calls the native Messages API (POST /v1/messages) and LLM_API_KEY falls
back to ANTHROPIC_API_KEY. Output: results/raw/llm_<model>_pass<N>.jsonl.

Usage:
  uv run run_llm.py --list-models
  uv run run_llm.py --limit 10
  uv run run_llm.py
  uv run run_llm.py --pass 2 --sample 300
  uv run run_llm.py --concurrency 8          # paid tier: fast accuracy run; latency then comes from a sequential subset
  uv run run_llm.py --dry-run --limit 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from bench.common import (
    DATA_DIR,
    RAW_DIR,
    RateLimiter,
    append_jsonl,
    done_ids,
    env,
    env_float,
    load_emails,
    post_with_retry,
    select_emails,
)

STRATEGY = "balanced"
ANSWER_LINE_SYSTEM = "Answer '1' (Click) or '0' (Don't Click)."
ANSWER_LINE_USER = "Should I click? Answer 1 or 0."
JSON_FORMAT_SYSTEM = (
    'Answer with a single JSON object and nothing else: {"click": 1 or 0, "phishing_probability": number between 0 and 1} '
    "where click 1 means Click and 0 means Don't Click, and phishing_probability is your probability that the email is phishing."
)
JSON_FORMAT_USER = 'Should I click? Reply with JSON only: {"click": 1 or 0, "phishing_probability": 0 to 1}'


def load_prompts() -> tuple[str, str]:
    path = DATA_DIR / "phishnchips" / "prompt_strategies.json"
    if not path.exists():
        sys.exit(f"{path} not found. Run prepare_data.py first.")
    strategies = json.loads(path.read_text(encoding="utf-8"))
    entry = next(s for s in strategies if s["name"] == STRATEGY)
    system, user = entry["system_prompt"], entry["user_prompt_template"]
    if ANSWER_LINE_SYSTEM not in system or ANSWER_LINE_USER not in user:
        sys.exit("The 'balanced' prompt changed upstream, refusing to guess the format line.")
    return system.replace(ANSWER_LINE_SYSTEM, JSON_FORMAT_SYSTEM), user.replace(ANSWER_LINE_USER, JSON_FORMAT_USER)


JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_answer(text: str) -> tuple[dict | None, str | None]:
    """Extract {"click", "phishing_probability"} from the model text. Returns (parsed, format_error)."""
    if text is None:
        return None, "empty response"
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    candidate = cleaned
    try:
        obj = json.loads(candidate)
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
    try:
        click = int(obj["click"])
        prob = float(obj["phishing_probability"])
    except (KeyError, TypeError, ValueError):
        return None, "missing or non-numeric fields"
    if click not in (0, 1) or not (0.0 <= prob <= 1.0):
        return None, "values out of range"
    return {"click": click, "phishing_probability": prob}, None


def build_body(email: dict, model: str, system: str, user_tpl: str, extra: dict, provider: str = "openai") -> dict:
    user = user_tpl.replace("{email}", email["email_raw"])
    if provider == "anthropic":
        # Native Messages API. No thinking parameter: Haiku 4.5 runs without thinking when it is omitted.
        body = {
            "model": model,
            "max_tokens": 256,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    else:
        body = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
    body.update(extra)
    return body


def extract(data: dict, provider: str) -> tuple[str, dict]:
    """Return (text, usage{input_tokens, output_tokens}) from a provider response."""
    if provider == "anthropic":
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage", {})
        return text, {"input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}
    text = data["choices"][0]["message"]["content"]
    u = data.get("usage", {})
    return text, {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}


def list_models(base_url: str, api_key: str) -> None:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
    print(resp.status_code)
    try:
        for m in resp.json().get("data", []):
            print(" ", m.get("id"))
    except ValueError:
        print(resp.text[:1000])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pass", dest="pass_no", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1, help="parallel requests (paid tiers). Keep 1 for latency measurements.")
    args = parser.parse_args()

    provider = env("LLM_PROVIDER", "openai").lower()
    base_url = env("LLM_BASE_URL", required=True).rstrip("/")
    model = env("LLM_MODEL", required=True)
    extra = json.loads(env("LLM_EXTRA_BODY", "{}") or "{}")
    system, user_tpl = load_prompts()
    emails = select_emails(load_emails(), limit=args.limit, sample=args.sample)

    if args.dry_run:
        print(json.dumps(build_body(emails[0], model, system, user_tpl, extra, provider), indent=2, ensure_ascii=False))
        return

    api_key = env("LLM_API_KEY") or (env("ANTHROPIC_API_KEY") if provider == "anthropic" else "")
    if not api_key:
        sys.exit("Missing LLM_API_KEY (or ANTHROPIC_API_KEY with LLM_PROVIDER=anthropic) in .env.")
    if args.list_models:
        list_models(base_url, api_key)
        return

    price_in, price_out = env_float("LLM_PRICE_IN"), env_float("LLM_PRICE_OUT")
    if price_in is None or price_out is None:
        sys.exit("Set LLM_PRICE_IN and LLM_PRICE_OUT (USD per million tokens, list price) in .env.")

    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        url = f"{base_url}/v1/messages"
    else:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/chat/completions"
    out = RAW_DIR / f"llm_{model}_pass{args.pass_no}.jsonl"
    already = done_ids(out)
    todo = [e for e in emails if e["id"] not in already]
    limiter = RateLimiter(env_float("LLM_RPM", 0.0) or 0.0)
    print(f"model {model} pass {args.pass_no}: {len(todo)} emails to run ({len(already)} already done) -> {out}")

    started = time.monotonic()
    counters = {"ok": 0, "api_errors": 0, "format_errors": 0, "tok_in": 0, "tok_out": 0, "consecutive_failures": 0, "done": 0}
    lock = threading.Lock()
    stop = threading.Event()
    client = httpx.Client(timeout=120)

    def work(email: dict) -> None:
        if stop.is_set():
            return
        with lock:
            limiter.wait()
        body = build_body(email, model, system, user_tpl, extra, provider)
        resp, latency, attempts, error = post_with_retry(client, url, headers=headers, payload=body, log=lambda _m: None)
        record = {
            "id": email["id"],
            "y": email["y"],
            "pass": args.pass_no,
            "model": model,
            "provider": provider,
            "concurrency": args.concurrency,
            "ts": datetime.now(timezone.utc).isoformat(),
            "latency_s": latency,
            "attempts": attempts,
            "ok": False,
        }
        if resp is None or error:
            record["error"] = error or "unknown"
        else:
            try:
                data = resp.json()
                text, usage_std = extract(data, provider)
                record["raw"] = text
                record["usage"] = usage_std
                record["usage_raw"] = data.get("usage", {})  # keeps reasoning-token details when the provider sends them
                parsed, fmt_err = parse_answer(text)
                record["ok"] = True
                if parsed:
                    record["answer"] = parsed
                else:
                    record["format_error"] = fmt_err
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                record["error"] = f"bad response: {exc}: {resp.text[:300]}"
        with lock:
            append_jsonl(out, record)
            counters["done"] += 1
            if record["ok"]:
                counters["ok"] += 1
                counters["consecutive_failures"] = 0
                counters["tok_in"] += int(record["usage"]["input_tokens"] or 0)
                counters["tok_out"] += int(record["usage"]["output_tokens"] or 0)
                if "format_error" in record:
                    counters["format_errors"] += 1
            else:
                counters["api_errors"] += 1
                counters["consecutive_failures"] += 1
            i = counters["done"]
            if args.limit and args.limit <= 20 and record["ok"]:
                print(f"{email['id']} y={email['y']} -> {record.get('answer') or record.get('format_error')} {latency*1000:.0f} ms usage={record['usage']}", flush=True)
            elif i % 25 == 0 or i == len(todo):
                elapsed = time.monotonic() - started
                print(f"  {i}/{len(todo)} ok={counters['ok']} api_errors={counters['api_errors']} format_errors={counters['format_errors']} elapsed={elapsed:.0f}s", flush=True)
            if not record["ok"]:
                print(f"  {email['id']}: {record['error'][:160]}", flush=True)
            if counters["consecutive_failures"] >= 5 and not stop.is_set():
                print("5 consecutive failures (quota exhausted?). Stopping, rerun later to resume.", flush=True)
                stop.set()

    if args.concurrency <= 1:
        for email in todo:
            if stop.is_set():
                break
            work(email)
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            list(pool.map(work, todo))
    client.close()
    ok, api_errors, format_errors = counters["ok"], counters["api_errors"], counters["format_errors"]
    tok_in, tok_out = counters["tok_in"], counters["tok_out"]
    cost = tok_in / 1e6 * price_in + tok_out / 1e6 * price_out
    print(f"done: ok={ok} api_errors={api_errors} format_errors={format_errors} tokens in/out={tok_in}/{tok_out} list cost ~${cost:.4f}", flush=True)


if __name__ == "__main__":
    main()

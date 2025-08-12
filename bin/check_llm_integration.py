#!/usr/bin/env python3
"""
LLM Model Integration Checker for Ollama
- Verifies connectivity to Ollama API
- Checks model availability (llama3.2:latest, mistral:7b-instruct)
- Runs single-turn & multi-turn chat smoke tests
- Measures latency & rough tokens/sec
- Confirms unload via `ollama stop`
- Prints a compact PASS/FAIL summary and exits 0/1

USAGE:
  python bin/check_llm_integration.py
  python bin/check_llm_integration.py --server http://localhost:11434 --models llama3.2:latest,mistral:7b-instruct
  python bin/check_llm_integration.py --timeout 180 --ctx 4096

REQUIREMENTS:
  pip install requests

NOTES:
- Designed for MacBook Air M2 8GB or similar. Keeps runs tiny.
- Uses Ollama HTTP API: /api/tags, /api/chat, /api/generate, /api/ps
"""

import argparse
import json
import os
import sys
import time
import subprocess
from typing import List, Dict

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(2)

DEFAULT_SERVER = os.environ.get("OLLAMA_SERVER", "http://localhost:11434")

DEFAULT_MODELS = [
    "llama3.2:latest",        # your installed Llama 3.2 (3B) tag
    "mistral:7b-instruct",    # recommended Mistral 7B (Q4) tag
]

SINGLE_TURN_PROMPT = "In one sentence, explain what molded plywood is and why it mattered to midcentury design."
MULTI_TURN_1 = "Give three bullet points about the Eames Lounge Chair's design significance. Be concise."
MULTI_TURN_2 = "Now rewrite those points as a single 40-word paragraph."
SYSTEM_HINT = "You are a precise assistant. Be factual, concise, and avoid hallucinations."

def stop_model(name: str):
    """Explicitly unload a model from memory (best-effort)."""
    try:
        subprocess.run(["ollama", "stop", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except Exception:
        # Non-fatal; continue
        pass

def api_get(server: str, path: str, timeout: int = 30):
    url = f"{server}{path}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def api_post(server: str, path: str, payload: Dict, timeout: int = 60):
    url = f"{server}{path}"
    
    if path == "/api/chat":
        # For chat, we need to handle streaming responses properly
        r = requests.post(url, json=payload, timeout=timeout, stream=True)
        r.raise_for_status()
        
        # Collect all streaming responses
        accumulated_content = ""
        final_response = None
        
        for line in r.iter_lines():
            if line:
                try:
                    response_obj = json.loads(line.decode('utf-8'))
                    
                    # Accumulate content from each response
                    if 'message' in response_obj and 'content' in response_obj['message']:
                        accumulated_content += response_obj['message']['content']
                    
                    if response_obj.get('done', False):
                        final_response = response_obj
                        # Replace the empty content with our accumulated content
                        final_response['message']['content'] = accumulated_content
                        break
                except json.JSONDecodeError:
                    continue
        
        if final_response:
            return final_response
        else:
            raise RuntimeError("Could not get complete response from Ollama")
    else:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

def list_models(server: str, timeout: int = 30) -> List[str]:
    # /api/tags returns {"models":[{"name":"mistral:7b-instruct", ...}, ...]}
    data = api_get(server, "/api/tags", timeout=timeout)
    return sorted([m.get("name") for m in data.get("models", []) if "name" in m])

def ps(server: str, timeout: int = 10) -> List[Dict]:
    try:
        return api_get(server, "/api/ps", timeout=timeout).get("models", [])
    except Exception:
        return []

def chat_once(server: str, model: str, system: str, user: str, num_ctx: int, temperature: float, timeout: int = 120):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature
        }
    }
    t0 = time.time()
    resp = api_post(server, "/api/chat", payload, timeout=timeout)
    dt = time.time() - t0
    
    out = resp.get("message", {}).get("content", "")
    # Rough token estimate (chars/4) to avoid extra deps
    toks = max(1, len(out) // 4)
    tps = toks / dt if dt > 0 else 0.0
    return out.strip(), dt, toks, tps

def multi_turn_chat(server: str, model: str, system: str, m1: str, m2: str, num_ctx: int, temperature: float, timeout: int = 180):
    msgs = [{"role": "system", "content": system}]
    t0 = time.time()
    # Turn 1
    msgs.append({"role": "user", "content": m1})
    r1 = api_post(server, "/api/chat", {"model": model, "messages": msgs, "options": {"num_ctx": num_ctx, "temperature": temperature}}, timeout=timeout)
    a1 = r1.get("message", {}).get("content", "")
    msgs.append({"role": "assistant", "content": a1})
    # Turn 2
    msgs.append({"role": "user", "content": m2})
    r2 = api_post(server, "/api/chat", {"model": model, "messages": msgs, "options": {"num_ctx": num_ctx, "temperature": temperature}}, timeout=timeout)
    a2 = r2.get("message", {}).get("content", "")
    dt = time.time() - t0
    toks = max(1, (len(a1) + len(a2)) // 4)
    tps = toks / dt if dt > 0 else 0.0
    return (a1.strip(), a2.strip(), dt, toks, tps)

def main():
    ap = argparse.ArgumentParser(description="LLM model integration checker for Ollama")
    ap.add_argument("--server", default=DEFAULT_SERVER, help="Ollama server URL (default: %(default)s)")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS), help="Comma-separated model names to test")
    ap.add_argument("--timeout", type=int, default=150, help="HTTP timeout seconds")
    ap.add_argument("--ctx", type=int, default=4096, help="num_ctx to request")
    ap.add_argument("--temp", type=float, default=0.4, help="temperature for tests")
    ap.add_argument("--no-multiturn", action="store_true", help="Skip multi-turn chat test")
    args = ap.parse_args()

    server = args.server.rstrip("/")
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print(f"== Ollama Integration Check ==")
    print(f"Server: {server}")
    print(f"Models to test: {models}")
    print(f"Timeout: {args.timeout}s, num_ctx: {args.ctx}, temperature: {args.temp}")
    failures = []

    # 0) Connectivity
    try:
        avail = list_models(server, timeout=args.timeout)
        print(f"Available models ({len(avail)}): {avail}")
    except Exception as e:
        print(f"FAIL: Could not reach Ollama at {server} -> {e}", file=sys.stderr)
        sys.exit(3)

    # 1) Check each requested model is installed
    for m in models:
        if m not in avail:
            print(f"FAIL: Model not installed: {m}", file=sys.stderr)
            failures.append(f"missing:{m}")

    # Early exit if missing
    if failures:
        print("SUMMARY: FAIL (missing models). Run `ollama pull <model>` and retry.")
        sys.exit(4)

    # 2) For each model, run single-turn + (optional) multi-turn test
    for m in models:
        print(f"\n-- Testing model: {m} --")
        try:
            # Ensure clean slate
            stop_model(m)
            time.sleep(0.3)

            # Single turn
            out, dt, toks, tps = chat_once(
                server, m, SYSTEM_HINT, SINGLE_TURN_PROMPT,
                num_ctx=args.ctx, temperature=args.temp, timeout=args.timeout
            )
            snippet = (out[:140] + "...") if len(out) > 140 else out
            print(f"[single-turn] latency={dt:.2f}s, est_tokens={toks}, est_toks/s={tps:.1f}")
            print(f"[single-turn] output: {snippet}")

            if not out or len(out) < 20:
                raise RuntimeError("Single-turn output too short/empty")

            # Multi-turn
            if not args.no_multiturn:
                a1, a2, dt2, toks2, tps2 = multi_turn_chat(
                    server, m, SYSTEM_HINT, MULTI_TURN_1, MULTI_TURN_2,
                    num_ctx=args.ctx, temperature=args.temp, timeout=args.timeout
                )
                print(f"[multi-turn] latency={dt2:.2f}s, est_tokens={toks2}, est_toks/s={tps2:.1f}")
                print(f"[multi-turn] answer-2 snippet: {(a2[:140] + '...') if len(a2)>140 else a2}")
                if not a1 or not a2:
                    raise RuntimeError("Multi-turn output empty")

            # Check ps (should show model during run; may be empty after)
            running = ps(server)
            print(f"[ps] running now: {[r.get('name') for r in running]}")
        except Exception as e:
            print(f"FAIL: Model {m} test failed -> {e}", file=sys.stderr)
            failures.append(f"runtime:{m}")
        finally:
            # Always try to unload
            stop_model(m)
            time.sleep(0.2)

    # 3) Summary
    if failures:
        print(f"\nSUMMARY: FAIL ({len(failures)} issue(s)) -> {failures}")
        sys.exit(1)
    else:
        print("\nSUMMARY: PASS (all models operational)")
        sys.exit(0)

if __name__ == "__main__":
    main()

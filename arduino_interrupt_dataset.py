#!/usr/bin/env python3
"""
Arduino Interrupt Dataset Builder (GitHub REST v3)

What it does
------------
- Runs multiple GitHub Code Search queries focused on Arduino interrupt usage.
- Downloads matching source files and saves them under ./dataset/code/
- Writes a JSONL metadata file with rich fields (repo, path, sha, license, stars, query, size, url, etc.).
- De-duplicates files across queries.
- Optionally filters to repos with a known open-source license (--license-filter).
- Heuristically tags the MCU/platform family (AVR, ESP32, ESP8266, STM32, Teensy, RP2040, Generic).

Usage
-----
export GITHUB_TOKEN=ghp_...  # required
python arduino_interrupt_dataset.py --max-pages 10 --out ./arduino_interrupt_dataset

Notes
-----
- GitHub Code Search caps results at ~1000 per query. We shard queries by keyword to increase coverage.
- Be mindful of GitHub's ToS and repository licenses when redistributing code. This tool records license info.
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("ERROR: Please set GITHUB_TOKEN environment variable.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "arduino-interrupt-dataset/1.0",
}

SEARCH_URL = "https://api.github.com/search/code"
CONTENTS_API = "https://api.github.com/repos/{repo}/contents/{path}"
LICENSE_API = "https://api.github.com/repos/{repo}/license"
REPO_API    = "https://api.github.com/repos/{repo}"

# ---- Query Shards: broaden beyond just .ino and AVR-style attachInterrupt ----
QUERY_SHARDS = [
    # Classic Arduino (AVR) style
    'extension:ino attachInterrupt "void setup" "void loop"',
    'extension:ino digitalPinToInterrupt "void setup" "void loop"',
    'extension:ino ISR( "void setup" "void loop"',
    'extension:ino cli() sei()',
    # C++ files in Arduino libs/examples (many sketches are .cpp/.h)
    'language:C++ attachInterrupt "void setup" "void loop" path:/examples/',
    'language:C++ digitalPinToInterrupt path:/examples/',
    'language:C++ ISR(',
    # ESP32 specifics
    'extension:ino gpio_isr_handler_add',
    'extension:ino esp_intr_alloc',
    'language:C++ "attachInterruptArg"',
    # ESP8266
    'extension:ino ICACHE_RAM_ATTR attachInterrupt',
    # STM32 (Arduino_Core_STM32 or HAL)
    'language:C++ EXTI_IRQHandler extension:ino',
    'language:C++ HAL_NVIC_SetPriority "EXTI"',
    # Teensy
    'language:C++ attachInterrupt NVIC',
    # RP2040 / Pico SDK (when used in Arduino cores)
    'language:C++ irq_set_enabled',
]

# Heuristic platform tags
PLATFORM_RULES = [
    ("ESP32", ["ESP32", "gpio_isr_handler_add", "esp_intr_alloc", "attachInterruptArg"]),
    ("ESP8266", ["ESP8266", "ICACHE_RAM_ATTR"]),
    ("STM32", ["STM32", "HAL_NVIC", "EXTI", "HAL_GPIO_EXTI", "EXTI_IRQHandler"]),
    ("Teensy", ["TEENSYDUINO", "NVIC_", "KINETIS", "TEENSY"]),
    ("RP2040", ["RP2040", "Pico", "irq_set_enabled", "PIO", "hardware_irq"]),
    ("AVR", ["ISR(", "cli()", "sei()", "__vector_", "EIMSK", "EICRA", "PCICR"]),
]

# Permissive-ish license keys (non-exhaustive); extend as needed.
PERMISSIVE_LICENSE_KEYS = {
    "mit", "bsd-2-clause", "bsd-3-clause", "apache-2.0", "isc", "cc0-1.0", "unlicense", "zlib"
}


def rate_limit_sleep(resp: requests.Response):
    """Back off when approaching rate limits."""
    try:
        remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
        reset_at = int(resp.headers.get("X-RateLimit-Reset", "0"))
    except ValueError:
        remaining, reset_at = 1, 0

    if remaining <= 1:
        now = int(time.time())
        wait = max(0, reset_at - now) + 5
        print(f"[rate-limit] Remaining={remaining}. Sleeping {wait}s until reset.", file=sys.stderr)
        time.sleep(wait)


def robust_get(url: str, **kwargs) -> requests.Response:
    """GET with simple retry/backoff on 502/503/504 and rate limits."""
    for attempt in range(6):
        resp = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
        if resp.status_code in (502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            rate_limit_sleep(resp)
            continue
        return resp
    return resp


def repo_license(repo_full_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (license_key, spdx_id) if available."""
    resp = robust_get(LICENSE_API.format(repo=repo_full_name))
    if resp.status_code == 200:
        data = resp.json()
        lic = data.get("license") or {}
        return lic.get("key"), lic.get("spdx_id")
    else:
        # Fallback to repo endpoint (sometimes gives partial license info)
        r2 = robust_get(REPO_API.format(repo=repo_full_name))
        if r2.status_code == 200:
            lic = (r2.json() or {}).get("license") or {}
            return lic.get("key"), lic.get("spdx_id")
    return None, None


def detect_platform(text: str) -> str:
    upper = text.upper()
    for label, needles in PLATFORM_RULES:
        for n in needles:
            if n.upper() in upper:
                return label
    return "Generic"


def contents_download(repo: str, path: str, ref: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """Download file via the Contents API (base64). Returns (text, size).

    Falls back to raw.githubusercontent.com using the provided ref if the
    Contents API is unavailable or returns non-base64 content.
    """
    url = CONTENTS_API.format(repo=repo, path=path)
    params = {"ref": ref} if ref else {}
    resp = robust_get(url, params=params)
    if resp.status_code == 200:
        data = resp.json()
        if not isinstance(data, list) and data.get("encoding") == "base64":
            try:
                raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            except Exception:
                raw = None
            else:
                return raw, data.get("size")

    # Fallback to raw if we have a plausible ref (branch/tag/commit)
    if ref:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        try:
            r2 = requests.get(raw_url, timeout=30)
            if r2.status_code == 200:
                return r2.text, len(r2.content)
        except Exception:
            pass

    return None, None


def search_query(q: str, page: int, per_page: int = 100) -> Dict:
    params = {"q": q, "per_page": per_page, "page": page}
    resp = robust_get(SEARCH_URL, params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Search error {resp.status_code}: {resp.text[:200]}")
    rate_limit_sleep(resp)
    return resp.json()


def build_dataset(
    out_dir: Path,
    max_pages: int,
    license_filter: bool,
    min_stars: int,
    limit_shards: Optional[int] = None,
    max_items: Optional[int] = None,
    query_override: Optional[str] = None,
    no_content_guard: bool = False,
    sleep_seconds: float = 1.5,
    per_page: int = 100,
    skip_license_lookup: bool = False,
    debug: bool = False,
    max_processed: Optional[int] = None,
):
    out_code = out_dir / "code"
    out_meta = out_dir / "metadata.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_code.mkdir(parents=True, exist_ok=True)

    seen_keys: Set[str] = set()

    # Determine which queries to run
    if query_override:
        shards: List[str] = [query_override]
    elif limit_shards is not None:
        shards = QUERY_SHARDS[: max(0, limit_shards)]
    else:
        shards = QUERY_SHARDS

    num_written = 0
    num_processed = 0

    with out_meta.open("w", encoding="utf-8") as meta_f:
        for shard_idx, query in enumerate(shards, 1):
            print(f"\n[shard {shard_idx}/{len(QUERY_SHARDS)}] {query}")
            for page in range(1, max_pages + 1):
                try:
                    data = search_query(query, page, per_page=per_page)
                except RuntimeError as e:
                    print(f"  page {page}: {e}")
                    break

                items = data.get("items", [])
                if not items:
                    print(f"  page {page}: 0 results, stopping shard.")
                    break

                print(f"  page {page}: {len(items)} items")
                for idx, it in enumerate(items, 1):
                    repo = it["repository"]["full_name"]
                    path = it["path"]
                    sha  = it.get("sha")
                    key  = f"{repo}::{path}::{sha}"
                    if key in seen_keys:
                        continue

                    if debug and idx % 5 == 0:
                        print(f"    processing item {idx}/{len(items)}: {repo}/{path}")

                    # Respect a hard cap on processed items (regardless of success)
                    if max_processed is not None and num_processed >= max_processed:
                        print(f"Reached max-processed={max_processed}; stopping early.")
                        return

                    # Repo gating (stars / license) for quality/legal filtering
                    stargazers = it["repository"].get("stargazers_count", 0)
                    if stargazers < min_stars:
                        continue

                    if not skip_license_lookup:
                        lic_key, lic_spdx = repo_license(repo)
                        if license_filter and lic_key and lic_key.lower() not in PERMISSIVE_LICENSE_KEYS:
                            continue
                    else:
                        lic_key, lic_spdx = None, None

                    # Prefer repository default_branch as ref; blob SHA from search may not work for Contents API
                    default_branch = (it.get("repository") or {}).get("default_branch")
                    text, fsize = contents_download(repo, path, default_branch)
                    if not text:
                        if debug:
                            print(f"    skip: failed to fetch contents for {repo}/{path} ref={default_branch}")
                        num_processed += 1
                        continue

                    # Minimal interrupt presence guard (extra safety)
                    if not no_content_guard:
                        if not any(
                            x in text
                            for x in [
                                "attachInterrupt",
                                "ISR(",
                                "gpio_isr_handler_add",
                                "interrupt",
                                "digitalPinToInterrupt",
                            ]
                        ):
                            if debug:
                                print(f"    skip: content guard failed for {repo}/{path}")
                            num_processed += 1
                            continue

                    platform = detect_platform(text)

                    # Save code file (namespaced, stable)
                    safe_repo = repo.replace("/", "_")
                    fname = f"{safe_repo}__{sha[:8]}__{Path(path).name}"
                    out_path = out_code / fname
                    try:
                        out_path.write_text(text, encoding="utf-8")
                    except Exception as e:
                        print(f"    write failed: {out_path.name}: {e}")
                        num_processed += 1
                        continue

                    meta = {
                        "query": query,
                        "repo": repo,
                        "path": path,
                        "sha": sha,
                        "file_saved_as": out_path.name,
                        "size_bytes": fsize,
                        "stargazers": stargazers,
                        "license_key": lic_key,
                        "license_spdx": lic_spdx,
                        "html_url": it.get("html_url"),
                        "score": it.get("score"),
                        "platform": platform,
                        "has_attachInterrupt": "attachInterrupt" in text,
                        "has_ISR_macro": "ISR(" in text,
                        "has_digitalPinToInterrupt": "digitalPinToInterrupt" in text,
                        "has_gpio_isr_handler_add": "gpio_isr_handler_add" in text,
                    }
                    meta_f.write(json.dumps(meta, ensure_ascii=False) + "\n")
                    if debug:
                        print(f"    wrote: {out_path.name}")
                    seen_keys.add(key)
                    num_written += 1
                    num_processed += 1

                    if max_items and num_written >= max_items:
                        print(f"Reached max-items={max_items}; stopping early.")
                        return

                # Gentle pacing between pages
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="./arduino_interrupt_dataset", help="Output directory")
    p.add_argument("--max-pages", type=int, default=10, help="Pages per shard (100 results/page)")
    p.add_argument("--license-filter", action="store_true", help="Keep only permissive-license repos")
    p.add_argument("--min-stars", type=int, default=0, help="Discard repos with fewer than N stars")
    # Quick-test options
    p.add_argument("--shards", type=int, default=None, help="Process only the first N query shards")
    p.add_argument("--max-items", type=int, default=None, help="Stop after writing N items")
    p.add_argument("--query", type=str, default=None, help="Override shards with a single custom query")
    p.add_argument("--no-content-guard", action="store_true", help="Disable minimal interrupt presence guard")
    p.add_argument("--sleep-seconds", type=float, default=1.5, help="Seconds to sleep between pages (set 0 for speed)")
    p.add_argument("--per-page", type=int, default=100, help="Search results per page (1-100)")
    p.add_argument("--skip-license", action="store_true", help="Skip repo license lookup to speed up")
    p.add_argument("--debug", action="store_true", help="Print progress while iterating items")
    p.add_argument("--max-processed", type=int, default=None, help="Stop after processing N items regardless of writes")
    args = p.parse_args()

    out_dir = Path(args.out)
    build_dataset(
        out_dir,
        max_pages=args.max_pages,
        license_filter=args.license_filter,
        min_stars=args.min_stars,
        limit_shards=args.shards,
        max_items=args.max_items,
        query_override=args.query,
        no_content_guard=args.no_content_guard,
        sleep_seconds=args.sleep_seconds,
        per_page=args.per_page,
        skip_license_lookup=args.skip_license,
        debug=args.debug,
        max_processed=args.max_processed,
    )

    print("\nDone.")
    print(f"- Code files: {out_dir/'code'}")
    print(f"- Metadata : {out_dir/'metadata.jsonl'}")

if __name__ == "__main__":
    main()

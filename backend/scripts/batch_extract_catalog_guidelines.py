"""
Batch Live Fetch + Gemini LLM Guideline Extraction for the 50 Catalog Journals.
Fetches each journal's official author guidelines URL via safe_fetch_url,
cleans & chunks the HTML, runs orchestrate_extraction with GeminiLLMClient,
merges grounded live-extracted rules into backend/seed/guideline_rules/<slug>.json,
and prints a full per-journal and summary report.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.guidelines.chunker import build_text_chunks
from app.services.guidelines.cleaner import CleanError, clean_guideline_content
from app.services.guidelines.extractor import orchestrate_extraction
from app.services.guidelines.fetcher import FetchError, safe_fetch_url
from app.services.guidelines.llm.gemini_client import GeminiLLMClient
from app.services.guidelines.schema import GuidelineRuleSchema

RULES_DIR = BACKEND_DIR / "seed" / "guideline_rules"
# Exclude standalone non-50-catalog seed files if desired, or process all that have sourceUrl
NON_CATALOG_FILES = {"nature.json", "springer_lncs.json"}


def deep_merge_rules(base: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Merges live-extracted rules over base template rules so live-extracted
    constraints take precedence while preserving unmentioned publisher template defaults.
    """
    merged = dict(base)
    for key, val in extracted.items():
        if key == "schemaVersion":
            merged[key] = 1
            continue
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_rules(merged[key], val)
        elif val is not None:
            merged[key] = val
    return merged


async def process_one_journal(
    file_path: Path,
    client: GeminiLLMClient,
    idx: int,
    total: int,
) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    name = data.get("name", file_path.stem)
    url = data.get("sourceUrl")
    if not url:
        return {"file": file_path.name, "name": name, "status": "skipped", "reason": "No sourceUrl"}

    t0 = time.perf_counter()
    try:
        fetch_res = await safe_fetch_url(url, check_robots=True, politeness_delay=True)
    except FetchError as fe:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] BLOCKED/FETCH_ERR  {file_path.name:<35} ({fe.code}: {fe.message[:60]}) [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "fetch_failed", "code": fe.code, "reason": fe.message}
    except Exception as e:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] FETCH_EXC        {file_path.name:<35} ({str(e)[:60]}) [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "fetch_failed", "code": "EXC", "reason": str(e)}

    # Check bot challenge warning
    if any(w.get("code") == "BOT_CHALLENGE_DETECTED" for w in fetch_res.warnings):
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] BOT_CHALLENGE    {file_path.name:<35} [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "bot_challenge", "reason": "Bot challenge page"}

    try:
        cleaned_text, clean_warnings, meta = clean_guideline_content(
            fetch_res.content, is_html=("html" in (fetch_res.content_type or "").lower())
        )
    except CleanError as ce:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] TOO_SHORT/EMPTY  {file_path.name:<35} ({ce.code}: {ce.message[:60]}) [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "too_short", "words": 0, "reason": ce.message}

    word_count = meta.get("wordCount", 0)
    if word_count < 60:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] TOO_SHORT ({word_count}w) {file_path.name:<35} (likely JS-rendered shell) [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "too_short", "words": word_count, "reason": f"Only {word_count} words"}

    chunks, _ = build_text_chunks(cleaned_text)
    try:
        draft, ext_warnings, _ = await orchestrate_extraction(chunks, client, source_text=cleaned_text)
    except Exception as e:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] LLM_ERROR        {file_path.name:<35} ({str(e)[:60]}) [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "llm_failed", "reason": str(e)}

    extracted_rules = draft.get("rules", {})
    extracted_fields = draft.get("fields", {})
    field_count = len(extracted_fields)

    if field_count == 0:
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[{idx:02d}/{total}] NO_RULES ({word_count}w) {file_path.name:<35} [{elapsed}s]", flush=True)
        return {"file": file_path.name, "name": name, "status": "no_rules", "words": word_count}

    # Merge live extracted rules over existing base rules and validate
    base_rules = data.get("rules", {"schemaVersion": 1})
    merged_rules = deep_merge_rules(base_rules, extracted_rules)
    validated = GuidelineRuleSchema.model_validate(merged_rules)

    data["sourceUrl"] = fetch_res.final_url or url
    data["rules"] = validated.model_dump(exclude_none=True)
    data["provenance"] = {
        "seeded": True,
        "liveExtracted": True,
        "sourceFile": file_path.name,
        "extractedFieldCount": field_count,
        "fields": extracted_fields,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    elapsed = round(time.perf_counter() - t0, 2)
    print(f"[{idx:02d}/{total}] LIVE_OK ({field_count:2d} fields, {word_count:4d}w) {file_path.name:<35} [{elapsed}s]", flush=True)
    return {
        "file": file_path.name,
        "name": name,
        "status": "live_ok",
        "fields": field_count,
        "words": word_count,
    }


async def main() -> None:
    files = sorted(p for p in RULES_DIR.glob("*.json") if p.name not in NON_CATALOG_FILES)
    total = len(files)
    print(f"Starting batch live fetch + Gemini extraction for {total} catalog journals...\n", flush=True)

    client = GeminiLLMClient()
    results: list[dict[str, Any]] = []

    for idx, file_path in enumerate(files, start=1):
        res = await process_one_journal(file_path, client, idx, total)
        results.append(res)

    live_ok = [r for r in results if r["status"] == "live_ok"]
    fetch_failed = [r for r in results if r["status"] == "fetch_failed"]
    bot_challenge = [r for r in results if r["status"] == "bot_challenge"]
    too_short = [r for r in results if r["status"] == "too_short"]
    no_rules = [r for r in results if r["status"] == "no_rules"]
    llm_failed = [r for r in results if r["status"] == "llm_failed"]

    print("\n" + "=" * 60)
    print("BATCH EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total catalog journals : {total}")
    print(f"Live fetch + LLM OK    : {len(live_ok)}")
    print(f"Fetch failed (403/etc) : {len(fetch_failed)}")
    print(f"Bot challenge          : {len(bot_challenge)}")
    print(f"JS-shell / too short   : {len(too_short)}")
    print(f"No rules extracted     : {len(no_rules)}")
    print(f"LLM failed             : {len(llm_failed)}")


if __name__ == "__main__":
    asyncio.run(main())


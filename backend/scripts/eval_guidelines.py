"""
Evaluation Harness for Guideline Extraction (Phase G11).
Runs extraction against the hand-labeled gold set and computes precision, recall,
coverage, hallucination rate, grounding quality, and latency.
Reference: Guideline Extraction Plan Section 8 (Phase G11), 10.16.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.guidelines.extractor import run_extraction_pipeline
from app.services.guidelines.llm.gemini_client import GeminiLLMClient
from app.services.guidelines.schema import GuidelineRuleSchema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval_guidelines")

DEFAULT_EVAL_DIR = BACKEND_DIR / "eval" / "guidelines"


def flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flattens a nested dictionary into dot-separated paths."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if k == "schemaVersion":
            continue
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and k != "keywords":
            out.update(flatten_dict(v, p))
        else:
            out[p] = v
    return out


def compare_field_values(gold_val: Any, pred_val: Any) -> bool:
    """Compares field values with normalization."""
    if gold_val is None and pred_val is None:
        return True
    if gold_val is None or pred_val is None:
        return False

    if isinstance(gold_val, list) and isinstance(pred_val, list):
        # Compare as sets
        return set(gold_val) == set(pred_val)

    if isinstance(gold_val, (int, float)) and isinstance(pred_val, (int, float)):
        return float(gold_val) == float(pred_val)

    if isinstance(gold_val, str) and isinstance(pred_val, str):
        return gold_val.strip().lower() == pred_val.strip().lower()

    return gold_val == pred_val


async def run_evaluation(
    eval_dir: Path = DEFAULT_EVAL_DIR,
    output_report: bool = True,
) -> dict[str, Any]:
    """Runs extraction evaluation across all test pairs."""
    txt_files = sorted(eval_dir.glob("*.txt"))
    if not txt_files:
        print(f"No test guideline .txt files found in {eval_dir}")
        return {}

    client = GeminiLLMClient()

    results = []
    total_gold_fields = 0
    total_pred_fields = 0
    total_exact_matches = 0
    total_hallucinations = 0
    total_low_confidence = 0
    total_tokens = 0
    total_latency = 0.0

    print(f"\n=======================================================")
    print(f"Running Guideline Extraction Evaluation ({len(txt_files)} samples)")
    print(f"=======================================================\n")

    for txt_file in txt_files:
        slug = txt_file.stem
        expected_file = eval_dir / f"{slug}.expected.json"
        if not expected_file.exists():
            logger.warning(f"Skipping {slug}: no matching .expected.json file found.")
            continue

        with open(txt_file, "r", encoding="utf-8") as f:
            text = f.read()

        with open(expected_file, "r", encoding="utf-8") as f:
            expected_data = json.load(f)

        # Validate expected rules against schema
        gold_rules = expected_data.get("rules", {})
        GuidelineRuleSchema.model_validate(gold_rules)

        gold_flat = flatten_dict(gold_rules)

        # Run extraction
        t0 = time.time()
        extract_res = await run_extraction_pipeline(text, is_html=False, client=client)
        latency = time.time() - t0
        total_latency += latency

        pred_rules = extract_res.draft.get("rules", {}) if extract_res.draft else {}
        pred_flat = flatten_dict(pred_rules)
        pred_fields_meta = extract_res.draft.get("fields", {}) if extract_res.draft else {}

        # Compute field matches
        matched = 0
        hallucinations = 0
        for path, val in pred_flat.items():
            if path in gold_flat:
                if compare_field_values(gold_flat[path], val):
                    matched += 1
            else:
                hallucinations += 1

        low_conf = sum(1 for f in pred_fields_meta.values() if isinstance(f, dict) and f.get("confidence") == "low")

        tokens = extract_res.input_tokens + extract_res.output_tokens
        total_tokens += tokens
        total_gold_fields += len(gold_flat)
        total_pred_fields += len(pred_flat)
        total_exact_matches += matched
        total_hallucinations += hallucinations
        total_low_confidence += low_conf

        sample_coverage = matched / len(gold_flat) if gold_flat else 0.0
        sample_precision = matched / len(pred_flat) if pred_flat else 0.0

        results.append({
            "slug": slug,
            "title": expected_data.get("journalTitle", slug),
            "gold_fields": len(gold_flat),
            "pred_fields": len(pred_flat),
            "matched": matched,
            "hallucinations": hallucinations,
            "coverage": sample_coverage,
            "precision": sample_precision,
            "latency": latency,
            "tokens": tokens,
        })

        print(f"[{slug}] Gold: {len(gold_flat)} | Extracted: {len(pred_flat)} | Matched: {matched} | Prec: {sample_precision:.1%} | Cov: {sample_coverage:.1%} | {latency:.2f}s")

    overall_precision = total_exact_matches / total_pred_fields if total_pred_fields else 0.0
    overall_coverage = total_exact_matches / total_gold_fields if total_gold_fields else 0.0
    overall_hallucination_rate = total_hallucinations / total_pred_fields if total_pred_fields else 0.0

    print(f"\n=======================================================")
    print(f"Overall Results Summary")
    print(f"=======================================================")
    print(f"Precision:           {overall_precision:.1%}")
    print(f"Coverage (Recall):   {overall_coverage:.1%}")
    print(f"Hallucination Rate: {overall_hallucination_rate:.1%}")
    print(f"Avg Latency:         {total_latency / len(results):.2f}s per page")
    print(f"Total Tokens:        {total_tokens}")
    print(f"=======================================================\n")

    if output_report:
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = eval_dir.parent / f"results_guidelines_{report_date}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Guideline Extraction Evaluation Results ({report_date})\n\n")
            f.write(f"- **Evaluated Samples:** {len(results)}\n")
            f.write(f"- **Overall Precision:** {overall_precision:.1%}\n")
            f.write(f"- **Overall Coverage (Recall):** {overall_coverage:.1%}\n")
            f.write(f"- **Hallucination Rate:** {overall_hallucination_rate:.1%}\n")
            f.write(f"- **Average Latency:** {total_latency / len(results):.2f} s\n")
            f.write(f"- **Total Tokens:** {total_tokens}\n\n")
            f.write("### Per-Journal Breakdown\n\n")
            f.write("| Journal / Venue | Gold Fields | Extracted | Matched | Precision | Coverage | Latency |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for r in results:
                f.write(f"| {r['title']} | {r['gold_fields']} | {r['pred_fields']} | {r['matched']} | {r['precision']:.1%} | {r['coverage']:.1%} | {r['latency']:.2f}s |\n")
        print(f"Wrote report to {report_path}")

    return {
        "precision": overall_precision,
        "coverage": overall_coverage,
        "hallucination_rate": overall_hallucination_rate,
        "latency_avg": total_latency / len(results) if results else 0,
        "tokens": total_tokens,
    }


if __name__ == "__main__":
    asyncio.run(run_evaluation())

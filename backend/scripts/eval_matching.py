import argparse
import csv
import datetime
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.embeddings_config import build_journal_lexical_text, build_journal_text
from app.db.models.journal import Journal
from app.db.session import SessionLocal
from app.services.bm25 import BM25Index
from app.services.embedding import JournalEmbedder
from app.services.matching import (
    build_query_text,
    compute_vectorized_cosine_similarity,
    normalize_cosine_for_hybrid,
    search_matching_journals,
)

BENCHMARK_MODELS = [
    "BAAI/bge-base-en-v1.5",
    "sentence-transformers/all-mpnet-base-v2",
    "allenai/specter2_base",
    "allenai-specter",
]


def _load_cases(test_cases_path: Path) -> list[dict]:
    if not test_cases_path.exists():
        print(f"Error: Test cases file not found at {test_cases_path}", file=sys.stderr)
        sys.exit(1)
    with open(test_cases_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _summarize_rankings(
    ranked_lists: list[list[tuple[str, float, float]]],
    cases: list[dict],
) -> dict:
    """Computes Top-K, MRR, Mean Top Cosine Sim, Mean Min Cosine Sim, and Mean 1-5 Gap."""
    n = len(cases)
    top_1_hits = 0
    top_3_hits = 0
    top_5_hits = 0
    mrr_sum = 0.0
    top_cos_list = []
    min_cos_list = []
    top_hybrid_list = []
    gap_1_5_list = []
    per_case = []

    for idx, (case, ranking) in enumerate(zip(cases, ranked_lists), start=1):
        title = case.get("title", "").strip()
        true_journal = case.get("true_journal_title", "").strip()

        true_rank = None
        for rank_idx, (j_title, _score, _cos) in enumerate(ranking, start=1):
            if j_title.strip().lower() == true_journal.lower():
                true_rank = rank_idx
                break

        rr = (1.0 / true_rank) if true_rank is not None else 0.0
        if true_rank == 1:
            top_1_hits += 1
        if true_rank is not None and true_rank <= 3:
            top_3_hits += 1
        if true_rank is not None and true_rank <= 5:
            top_5_hits += 1
        mrr_sum += rr

        top_score = ranking[0][1] if ranking else 0.0
        top_cos = ranking[0][2] if ranking else 0.0
        min_cos = min((r[2] for r in ranking), default=0.0)
        gap_1_5 = (ranking[0][1] - ranking[4][1]) if len(ranking) >= 5 else 0.0

        top_hybrid_list.append(top_score)
        top_cos_list.append(top_cos)
        min_cos_list.append(min_cos)
        gap_1_5_list.append(gap_1_5)

        per_case.append(
            {
                "id": idx,
                "title": title,
                "true_journal": true_journal,
                "true_rank": true_rank,
                "reciprocal_rank": rr,
                "top_score": top_score,
                "top_cos": top_cos,
                "gap_1_5": gap_1_5,
                "top_3_predictions": [r[0] for r in ranking[:3]],
            }
        )

    return {
        "n": n,
        "top_1_hits": top_1_hits,
        "top_3_hits": top_3_hits,
        "top_5_hits": top_5_hits,
        "top_1_acc": (top_1_hits / n) * 100 if n > 0 else 0.0,
        "top_3_acc": (top_3_hits / n) * 100 if n > 0 else 0.0,
        "top_5_acc": (top_5_hits / n) * 100 if n > 0 else 0.0,
        "mrr": (mrr_sum / n) if n > 0 else 0.0,
        "avg_top_cos": (sum(top_cos_list) / n) if n > 0 else 0.0,
        "avg_min_cos": (sum(min_cos_list) / n) if n > 0 else 0.0,
        "avg_top_score": (sum(top_hybrid_list) / n) if n > 0 else 0.0,
        "avg_gap_1_5": (sum(gap_1_5_list) / n) if n > 0 else 0.0,
        "per_case": per_case,
    }


def run_evaluation(
    test_cases_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    if test_cases_path is None:
        test_cases_path = BACKEND_DIR / "eval" / "test_cases.csv"
    if output_dir is None:
        output_dir = BACKEND_DIR / "eval"

    output_dir.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(test_cases_path)
    print(f"Loaded {len(cases)} evaluation test cases from {test_cases_path.name}.")

    print(f"Initializing JournalEmbedder ({settings.EMBEDDING_MODEL})...")
    embedder = JournalEmbedder()
    embedder.load()

    ranked_lists: list[list[tuple[str, float, float]]] = []

    print("\nRunning hybrid evaluation against database embeddings...")
    print("-" * 100)

    with SessionLocal() as db:
        total_embedded = db.execute(select(Journal).where(Journal.embedding.is_not(None))).scalars().all()
        catalog_size = len(total_embedded)

        for idx, case in enumerate(cases, 1):
            title = case.get("title", "").strip()
            abstract = case.get("abstract", "").strip()
            true_journal = case.get("true_journal_title", "").strip()

            query_text = build_query_text(title=title, abstract=abstract)
            query_vector = embedder.embed_query(query_text)

            matches = search_matching_journals(
                query_vector=query_vector,
                db=db,
                query_text=query_text,
                limit=50,
            )

            ranking = [(m.journal.journal_title, m.hybrid_score, m.raw_cosine) for m in matches]
            ranked_lists.append(ranking)

            true_rank = next(
                (r_idx for r_idx, m in enumerate(matches, 1) if m.journal.journal_title.strip().lower() == true_journal.lower()),
                None,
            )
            top_hybrid = matches[0].hybrid_score if matches else 0.0
            top_cos = matches[0].raw_cosine if matches else 0.0
            gap_1_5 = (matches[0].hybrid_score - matches[4].hybrid_score) if len(matches) >= 5 else 0.0
            rank_str = f"Rank {true_rank}" if true_rank else "Not in top 50"

            print(
                f"[{idx:02d}/{len(cases):02d}] {title[:38]:<38} | True: {true_journal[:28]:<28} | "
                f"{rank_str:<12} (Hybrid: {top_hybrid:.4f}, Cos: {top_cos:.4f}, Gap1-5: {gap_1_5:.4f})"
            )

    summary = _summarize_rankings(ranked_lists, cases)
    n = summary["n"]

    print("-" * 100)
    print(f"EVALUATION METRICS SUMMARY ({n} cases, {catalog_size} journals):")
    print(f"  Model          : {embedder.model_name} + BM25 ({settings.HYBRID_COSINE_WEIGHT:.1f}/{settings.HYBRID_BM25_WEIGHT:.1f})")
    print(f"  Top-1 Accuracy : {summary['top_1_acc']:.1f}% ({summary['top_1_hits']}/{n})")
    print(f"  Top-3 Accuracy : {summary['top_3_acc']:.1f}% ({summary['top_3_hits']}/{n})")
    print(f"  Top-5 Accuracy : {summary['top_5_acc']:.1f}% ({summary['top_5_hits']}/{n})")
    print(f"  MRR            : {summary['mrr']:.4f}")
    print(f"  Mean Top Cos   : {summary['avg_top_cos']:.4f}")
    print(f"  Mean Top Hybrid: {summary['avg_top_score']:.4f}")
    print(f"  Mean 1-5 Gap   : {summary['avg_gap_1_5']:.4f}")
    print("-" * 100)

    today_str = datetime.date.today().isoformat()
    report_path = output_dir / f"results_{today_str}.md"

    md_lines = [
        f"# Journal Matching Evaluation Results ({today_str})",
        "",
        "## Summary Metrics",
        "",
        f"- **Model**: `{embedder.model_name}` (768-dim) + Okapi BM25 (`{settings.HYBRID_COSINE_WEIGHT:.1f}` Cosine / `{settings.HYBRID_BM25_WEIGHT:.1f}` BM25)",
        f"- **Catalog Size**: {catalog_size} journals",
        f"- **Test Cases**: {n} realistic manuscripts",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Top-1 Accuracy** | **{summary['top_1_acc']:.1f}%** ({summary['top_1_hits']}/{n}) |",
        f"| **Top-3 Accuracy** | **{summary['top_3_acc']:.1f}%** ({summary['top_3_hits']}/{n}) |",
        f"| **Top-5 Accuracy** | **{summary['top_5_acc']:.1f}%** ({summary['top_5_hits']}/{n}) |",
        f"| **Mean Reciprocal Rank (MRR)** | **{summary['mrr']:.4f}** |",
        f"| **Mean Top Cosine Similarity** | `{summary['avg_top_cos']:.4f}` |",
        f"| **Mean Top Hybrid Score** | `{summary['avg_top_score']:.4f}` |",
        f"| **Mean Rank 1-5 Gap** | `{summary['avg_gap_1_5']:.4f}` |",
        "",
        "## Per-Case Breakdown",
        "",
        "| # | Paper Title | True Journal | True Rank | Top Hybrid | Top Cosine | Rank 1-5 Gap | Top Predicted Journal |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in summary["per_case"]:
        top_pred = r["top_3_predictions"][0] if r["top_3_predictions"] else "N/A"
        rank_display = f"**{r['true_rank']}**" if r["true_rank"] and r["true_rank"] <= 3 else str(r["true_rank"])
        md_lines.append(
            f"| {r['id']} | {r['title']} | {r['true_journal']} | {rank_display} | {r['top_score']:.4f} | {r['top_cos']:.4f} | {r['gap_1_5']:.4f} | {top_pred} |"
        )

    md_lines.extend(
        [
            "",
            "## Score Calibration Insights",
            "",
            f"- **Mean Top Cosine Similarity**: `{summary['avg_top_cos']:.4f}` (Mean Lowest in Pool: `{summary['avg_min_cos']:.4f}`)",
            f"- **Mean Gap between Rank 1 and Rank 5 (Hybrid)**: `{summary['avg_gap_1_5']:.4f}`",
            "- Relative ranking across the full catalog pool with hybrid dense cosine + Okapi BM25 avoids brittle single-pair similarity thresholds.",
            "",
        ]
    )

    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Results report written to {report_path}")

    return {
        "top_1_acc": summary["top_1_acc"],
        "top_3_acc": summary["top_3_acc"],
        "top_5_acc": summary["top_5_acc"],
        "mrr": summary["mrr"],
        "avg_top_sim": summary["avg_top_cos"],
        "avg_top_hybrid": summary["avg_top_score"],
        "avg_gap_1_5": summary["avg_gap_1_5"],
        "report_path": str(report_path),
    }


def run_benchmark_models(
    test_cases_path: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    if test_cases_path is None:
        test_cases_path = BACKEND_DIR / "eval" / "test_cases.csv"
    if output_dir is None:
        output_dir = BACKEND_DIR / "eval"

    output_dir.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(test_cases_path)

    with SessionLocal() as db:
        journals = db.execute(select(Journal).order_by(Journal.journal_id.asc())).scalars().all()

    journal_titles = [j.journal_title for j in journals]
    journal_texts = [build_journal_text(j.journal_title, j.aims_and_scope) for j in journals]
    lexical_docs = [
        build_journal_lexical_text(j.journal_title, j.aims_and_scope, j.subject_category)
        for j in journals
    ]
    bm25_index = BM25Index(lexical_docs)

    query_texts = [
        build_query_text(title=c.get("title", ""), abstract=c.get("abstract", ""))
        for c in cases
    ]
    bm25_per_case = [bm25_index.normalized_score(qt) for qt in query_texts]

    rows: list[dict] = []

    # 1. BM25-only baseline
    bm25_rankings = []
    for bm_scores in bm25_per_case:
        idxs = sorted(range(len(journals)), key=lambda i: (-float(bm_scores[i]), journals[i].journal_id))
        bm25_rankings.append([(journal_titles[i], float(bm_scores[i]), 0.0) for i in idxs])
    bm25_summary = _summarize_rankings(bm25_rankings, cases)
    rows.append({"model": "Okapi BM25 Only", "mode": "Lexical", **bm25_summary})

    # 2. Dense-only and Hybrid (0.7 / 0.3) per transformer candidate
    for model_name in BENCHMARK_MODELS:
        print(f"\n=== Benchmarking Model: {model_name} ===")
        try:
            embedder = JournalEmbedder(model_name=model_name)
            embedder.load()
        except Exception as exc:
            print(f"  [ERROR] Could not load {model_name}: {exc}", file=sys.stderr)
            continue

        doc_vecs = [
            embedder.embed_document(text, title=j.journal_title)
            for j, text in zip(journals, journal_texts)
        ]
        doc_matrix = np.asarray(doc_vecs, dtype=np.float64)

        dense_rankings = []
        hybrid_rankings = []

        for qt, bm_scores in zip(query_texts, bm25_per_case):
            q_vec = np.asarray(embedder.embed_query(qt), dtype=np.float64)
            cos_scores = compute_vectorized_cosine_similarity(doc_matrix, q_vec)
            norm_cos = normalize_cosine_for_hybrid(cos_scores)
            hyb_scores = (0.7 * norm_cos) + (0.3 * bm_scores)

            dense_idxs = sorted(
                range(len(journals)),
                key=lambda i: (-float(cos_scores[i]), journals[i].journal_id),
            )
            dense_rankings.append([(journal_titles[i], float(cos_scores[i]), float(cos_scores[i])) for i in dense_idxs])

            hyb_idxs = sorted(
                range(len(journals)),
                key=lambda i: (-float(hyb_scores[i]), -float(cos_scores[i]), journals[i].journal_id),
            )
            hybrid_rankings.append([(journal_titles[i], float(hyb_scores[i]), float(cos_scores[i])) for i in hyb_idxs])

        dense_summary = _summarize_rankings(dense_rankings, cases)
        hybrid_summary = _summarize_rankings(hybrid_rankings, cases)

        rows.append({"model": model_name, "mode": "Dense Only (1.0)", **dense_summary})
        rows.append({"model": model_name, "mode": "Hybrid (0.7 Norm-Cos + 0.3 BM25)", **hybrid_summary})

        print(
            f"  Dense Only -> Top-1: {dense_summary['top_1_acc']:.1f}% | "
            f"Top-3: {dense_summary['top_3_acc']:.1f}% | "
            f"Top-5: {dense_summary['top_5_acc']:.1f}% | MRR: {dense_summary['mrr']:.4f} | "
            f"Cos Range: [{dense_summary['avg_min_cos']:.4f}, {dense_summary['avg_top_cos']:.4f}]"
        )
        print(
            f"  Hybrid     -> Top-1: {hybrid_summary['top_1_acc']:.1f}% | "
            f"Top-3: {hybrid_summary['top_3_acc']:.1f}% | "
            f"Top-5: {hybrid_summary['top_5_acc']:.1f}% | MRR: {hybrid_summary['mrr']:.4f} | "
            f"Gap 1-5: {hybrid_summary['avg_gap_1_5']:.4f}"
        )

    out_path = output_dir / "model_benchmark_results.md"
    lines = [
        "# Asymmetric Retrieval & Hybrid BM25 Model Benchmark",
        "",
        f"- **Date**: {datetime.date.today().isoformat()}",
        f"- **Catalog**: {len(journals)} journals (chunked sliding windows for >512 tokens, intact natural text)",
        f"- **Test Cases**: {len(cases)} manuscripts",
        "",
        "| Model | Mode | Top-1 | Top-3 | Top-5 | MRR | Mean Top Cos | Mean Min Cos | Mean 1-5 Gap |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in rows:
        lines.append(
            f"| `{r['model']}` | {r['mode']} | "
            f"**{r['top_1_acc']:.1f}%** ({r['top_1_hits']}/{r['n']}) | "
            f"{r['top_3_acc']:.1f}% ({r['top_3_hits']}/{r['n']}) | "
            f"{r['top_5_acc']:.1f}% ({r['top_5_hits']}/{r['n']}) | "
            f"**{r['mrr']:.4f}** | {r['avg_top_cos']:.4f} | {r['avg_min_cos']:.4f} | {r['avg_gap_1_5']:.4f} |"
        )
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nBenchmark comparison written to {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate or benchmark journal matching models.")
    parser.add_argument(
        "--benchmark-models",
        action="store_true",
        help="Benchmark candidate pretrained models (dense-only and hybrid 0.7/0.3) in memory.",
    )
    args = parser.parse_args()

    if args.benchmark_models:
        run_benchmark_models()
    else:
        run_evaluation()

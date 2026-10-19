import csv
import datetime
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.embedding import SpecterEmbedder
from app.services.matching import build_query_text, search_matching_journals


def run_evaluation(
    test_cases_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    if test_cases_path is None:
        test_cases_path = BACKEND_DIR / "eval" / "test_cases.csv"
    if output_dir is None:
        output_dir = BACKEND_DIR / "eval"

    output_dir.mkdir(parents=True, exist_ok=True)

    if not test_cases_path.exists():
        print(f"Error: Test cases file not found at {test_cases_path}", file=sys.stderr)
        sys.exit(1)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cases = list(reader)

    print(f"Loaded {len(cases)} evaluation test cases from {test_cases_path.name}.")

    print("Initializing SpecterEmbedder...")
    embedder = SpecterEmbedder()
    embedder.load()

    results = []
    top_1_hits = 0
    top_3_hits = 0
    top_5_hits = 0
    mrr_sum = 0.0

    top_sims = []
    gap_1_5_list = []

    print("\nRunning evaluation on test cases...")
    print("-" * 90)

    with SessionLocal() as db:
        for idx, case in enumerate(cases, 1):
            title = case.get("title", "").strip()
            abstract = case.get("abstract", "").strip()
            true_journal = case.get("true_journal_title", "").strip()

            query_text = build_query_text(title=title, abstract=abstract)
            query_vector = embedder.embed_query(query_text)

            matches = search_matching_journals(query_vector=query_vector, db=db, limit=50)

            true_rank = None
            for rank_idx, (j, raw_sim, score, tag) in enumerate(matches, 1):
                if j.journal_title.strip().lower() == true_journal.lower():
                    true_rank = rank_idx
                    break

            if true_rank is not None:
                rr = 1.0 / true_rank
                if true_rank == 1:
                    top_1_hits += 1
                if true_rank <= 3:
                    top_3_hits += 1
                if true_rank <= 5:
                    top_5_hits += 1
            else:
                rr = 0.0

            mrr_sum += rr

            top_sim = matches[0][1] if len(matches) > 0 else 0.0
            gap_1_5 = (matches[0][1] - matches[4][1]) if len(matches) >= 5 else 0.0

            top_sims.append(top_sim)
            gap_1_5_list.append(gap_1_5)

            top_3_titles = [m[0].journal_title for m in matches[:3]]

            case_res = {
                "id": idx,
                "title": title,
                "true_journal": true_journal,
                "true_rank": true_rank,
                "reciprocal_rank": rr,
                "top_sim": top_sim,
                "gap_1_5": gap_1_5,
                "top_3_predictions": top_3_titles,
            }
            results.append(case_res)

            rank_str = f"Rank {true_rank}" if true_rank else "Not in top 50"
            print(f"[{idx:02d}/{len(cases):02d}] {title[:40]:<40} | True: {true_journal[:30]:<30} | {rank_str:<12} (Sim: {top_sim:.4f}, Gap1-5: {gap_1_5:.4f})")

    n = len(cases)
    top_1_acc = (top_1_hits / n) * 100 if n > 0 else 0.0
    top_3_acc = (top_3_hits / n) * 100 if n > 0 else 0.0
    top_5_acc = (top_5_hits / n) * 100 if n > 0 else 0.0
    mrr = (mrr_sum / n) if n > 0 else 0.0
    avg_top_sim = sum(top_sims) / n if n > 0 else 0.0
    avg_gap_1_5 = sum(gap_1_5_list) / n if n > 0 else 0.0

    print("-" * 90)
    print(f"EVALUATION METRICS SUMMARY ({n} cases):")
    print(f"  Top-1 Accuracy : {top_1_acc:.1f}% ({top_1_hits}/{n})")
    print(f"  Top-3 Accuracy : {top_3_acc:.1f}% ({top_3_hits}/{n})")
    print(f"  Top-5 Accuracy : {top_5_acc:.1f}% ({top_5_hits}/{n})")
    print(f"  MRR            : {mrr:.4f}")
    print(f"  Mean Top Sim   : {avg_top_sim:.4f}")
    print(f"  Mean 1-5 Gap   : {avg_gap_1_5:.4f}")
    print("-" * 90)

    # Save Markdown report
    today_str = datetime.date.today().isoformat()
    report_path = output_dir / f"results_{today_str}.md"

    md_lines = [
        f"# Journal Matching Evaluation Results ({today_str})",
        "",
        "## Summary Metrics",
        "",
        f"- **Model**: `{embedder.model_name}` (768-dim)",
        f"- **Catalog Size**: 50 journals",
        f"- **Test Cases**: {n} realistic manuscripts",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Top-1 Accuracy** | **{top_1_acc:.1f}%** ({top_1_hits}/{n}) |",
        f"| **Top-3 Accuracy** | **{top_3_acc:.1f}%** ({top_3_hits}/{n}) |",
        f"| **Top-5 Accuracy** | **{top_5_acc:.1f}%** ({top_5_hits}/{n}) |",
        f"| **Mean Reciprocal Rank (MRR)** | **{mrr:.4f}** |",
        f"| **Mean Top Similarity** | `{avg_top_sim:.4f}` |",
        f"| **Mean Rank 1-5 Gap** | `{avg_gap_1_5:.4f}` |",
        "",
        "## Per-Case Breakdown",
        "",
        "| # | Paper Title | True Journal | True Rank | Top Sim | Rank 1-5 Gap | Top Predicted Journal |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        top_pred = r["top_3_predictions"][0] if r["top_3_predictions"] else "N/A"
        rank_display = f"**{r['true_rank']}**" if r["true_rank"] and r["true_rank"] <= 3 else str(r["true_rank"])
        md_lines.append(
            f"| {r['id']} | {r['title']} | {r['true_journal']} | {rank_display} | {r['top_sim']:.4f} | {r['gap_1_5']:.4f} | {top_pred} |"
        )

    md_lines.extend([
        "",
        "## Score Calibration Insights",
        "",
        f"- **Mean Top Similarity**: `{avg_top_sim:.4f}`",
        f"- **Mean Gap between Rank 1 and Rank 5**: `{avg_gap_1_5:.4f}`",
        "- Cosine distance in SPECTER space typically ranges between 0.65 and 0.90 for domain-relevant scientific texts.",
        "- Clamping raw similarity to `[0.0, 1.0]` and mapping to `0..100%` provides intuitive UI sorting, while ordinal ranking guarantees user relevance.",
        "",
    ])

    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Results report written to {report_path}")

    return {
        "top_1_acc": top_1_acc,
        "top_3_acc": top_3_acc,
        "top_5_acc": top_5_acc,
        "mrr": mrr,
        "avg_top_sim": avg_top_sim,
        "avg_gap_1_5": avg_gap_1_5,
        "report_path": str(report_path),
    }


if __name__ == "__main__":
    run_evaluation()

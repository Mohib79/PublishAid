import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.core.config import settings
from app.core.embeddings_config import build_journal_text
from app.db.models.journal import Journal
from app.db.session import SessionLocal
from app.services.embedding import JournalEmbedder


def embed_journals(
    force: bool = False,
    limit: int | None = None,
    batch_size: int = 16,
    model_name: str | None = None,
):
    target_model = model_name or settings.EMBEDDING_MODEL
    print(f"Loading embedding model: {target_model}...")
    embedder = JournalEmbedder(model_name=target_model)
    embedder.load()

    with SessionLocal() as session:
        query = select(Journal).order_by(Journal.journal_id.asc())
        if not force:
            query = query.where(Journal.embedding.is_(None))
        if limit is not None:
            query = query.limit(limit)

        journals = session.execute(query).scalars().all()
        total = len(journals)
        print(f"Found {total} journals to embed (model={target_model}, force={force}, limit={limit}).")

        if total == 0:
            print("No journals need embedding.")
            return

        for i in range(0, total, batch_size):
            batch = journals[i : i + batch_size]
            print(
                f"Embedding batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} "
                f"({len(batch)} items)..."
            )

            for j in batch:
                text = build_journal_text(j.journal_title, j.aims_and_scope)
                j.embedding = embedder.embed_document(text, title=j.journal_title)
                j.embedding_model = target_model

            session.commit()
            print(f"  [OK] Saved embeddings for {len(batch)} journals.")

        print(f"Embedding completed successfully for {total} journals using '{target_model}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-compute and save journal embeddings.")
    parser.add_argument("--force", action="store_true", help="Re-embed journals even if they already have an embedding")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of journals to embed")
    parser.add_argument("--batch-size", type=int, default=16, help="Commit batch size for embedding generation")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional HuggingFace/SentenceTransformer model name (defaults to settings.EMBEDDING_MODEL)",
    )
    args = parser.parse_args()

    embed_journals(
        force=args.force,
        limit=args.limit,
        batch_size=args.batch_size,
        model_name=args.model,
    )

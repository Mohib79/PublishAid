import argparse
import sys
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.journal import Journal

MODEL_NAME = "allenai-specter"

def embed_journals(force: bool = False, limit: int | None = None, batch_size: int = 16):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "sentence-transformers is not installed. Please install requirements-embeddings.txt "
            "(`pip install -r requirements-embeddings.txt`) before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading embedding model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    print(f"Model output dimension: {dim}")

    if dim != 768:
        print(f"Error: Model output dimension is {dim}, expected 768. Aborting.", file=sys.stderr)
        sys.exit(1)

    with SessionLocal() as session:
        query = select(Journal)
        if not force:
            query = query.where(Journal.embedding.is_(None))
        if limit is not None:
            query = query.limit(limit)

        journals = session.execute(query).scalars().all()
        total = len(journals)
        print(f"Found {total} journals to embed (force={force}, limit={limit}).")

        if total == 0:
            print("No journals need embedding.")
            return

        for i in range(0, total, batch_size):
            batch = journals[i : i + batch_size]
            texts = [f"{j.journal_title}. {j.aims_and_scope}" for j in batch]
            print(f"Embedding batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} ({len(batch)} items)...")

            embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)

            for j, emb in zip(batch, embeddings):
                j.embedding = emb.tolist()
                j.embedding_model = MODEL_NAME

            session.commit()
            print(f"  [OK] Saved embeddings for {len(batch)} journals.")

        print(f"Embedding completed successfully for {total} journals.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate embeddings for journals.")
    parser.add_argument("--force", action="store_true", help="Re-embed journals even if they already have an embedding")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of journals to embed")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for embedding generation")
    args = parser.parse_args()

    embed_journals(force=args.force, limit=args.limit, batch_size=args.batch_size)

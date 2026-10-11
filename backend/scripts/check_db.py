import sys
from sqlalchemy import text
from app.db.session import engine

def main():
    print("Connecting to database...")
    try:
        with engine.connect() as conn:
            # Check basic connectivity
            conn.execute(text("SELECT 1"))
            print("[OK] Successfully executed 'SELECT 1'.")

            # Check PostgreSQL version
            version_row = conn.execute(text("SELECT version();")).scalar()
            print(f"[OK] PostgreSQL Version: {version_row}")

            # Check pgvector extension status
            ext_row = conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            ).fetchone()

            if ext_row:
                print(f"[OK] Extension 'vector' is installed (version: {ext_row[1]}).")
            else:
                print("[!] Extension 'vector' is NOT yet installed (will be created in Alembic migration).")

        print("Database check completed successfully.")
        sys.exit(0)
    except Exception as e:
        print(f"[FAIL] Database connection failed: {e}", file=sys.stderr)

        sys.exit(1)

if __name__ == "__main__":
    main()

import os
import sys
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.journal import Journal
from app.db.models.guideline_rule import GuidelineRule

def seed_dev_data():
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "production":
        print("Refusing to seed dev data: APP_ENV is set to 'production'.", file=sys.stderr)
        sys.exit(1)

    print(f"Seeding development data (APP_ENV={app_env})...")

    with SessionLocal() as session:
        try:
            # 1. Demo Researcher
            researcher_email = "researcher@publishaid.test"
            researcher = session.execute(
                select(User).where(User.email == researcher_email)
            ).scalar_one_or_none()

            if not researcher:
                researcher = User(
                    full_name="Dr. Alex Rivera",
                    email=researcher_email,
                    password_hash="placeholder_hash_dev_only",
                    role="researcher",
                )
                session.add(researcher)
                session.flush()
                print("[OK] Created demo researcher: researcher@publishaid.test")
            else:
                print("  Demo researcher already exists.")

            # 2. Demo Admin
            admin_email = "admin@publishaid.test"
            admin = session.execute(
                select(User).where(User.email == admin_email)
            ).scalar_one_or_none()

            if not admin:
                admin = User(
                    full_name="Admin Supervisor",
                    email=admin_email,
                    password_hash="placeholder_hash_dev_only",
                    role="admin",
                )
                session.add(admin)
                session.flush()
                print("[OK] Created demo admin: admin@publishaid.test")
            else:
                print("  Demo admin already exists.")

            # 3. Demo Project
            proj_title = "Deep Learning Architectures for Automated Manuscript Formatting"
            demo_project = session.execute(
                select(Project).where(
                    Project.user_id == researcher.user_id,
                    Project.project_title == proj_title,
                )
            ).scalar_one_or_none()

            if not demo_project:
                demo_project = Project(
                    user_id=researcher.user_id,
                    project_title=proj_title,
                    manuscript_abstract=(
                        "This paper explores transformer-based architectures for automated parsing "
                        "and structural transformation of academic manuscripts across IEEE and Elsevier formats."
                    ),
                    summary_text="Project draft focusing on automated LaTeX and DOCX restructuring.",
                )
                session.add(demo_project)
                session.flush()
                print("[OK] Created demo project.")
            else:
                print("  Demo project already exists.")

            # 4. Sample GuidelineRule for a seeded journal
            target_journal = session.execute(
                select(Journal).limit(1)
            ).scalar_one_or_none()

            target_journal_id = target_journal.journal_id if target_journal else None

            existing_rule = None
            if target_journal_id:
                existing_rule = session.execute(
                    select(GuidelineRule).where(
                        GuidelineRule.journal_id == target_journal_id,
                        GuidelineRule.is_active == True,
                    )
                ).scalar_one_or_none()

            if not existing_rule and target_journal_id:
                sample_rules = {
                    "max_word_count": 8000,
                    "max_abstract_words": 250,
                    "citation_style": "IEEE",
                    "required_sections": [
                        "Abstract",
                        "Introduction",
                        "Methodology",
                        "Conclusion",
                        "References",
                    ],
                    "column_layout": "double",
                    "required_statements": [
                        "Conflict of Interest",
                        "Data Availability",
                    ],
                    "font": {"family": "Times New Roman", "size_pt": 10},
                    "margins_cm": {
                        "top": 2.5,
                        "bottom": 2.5,
                        "left": 2.0,
                        "right": 2.0,
                    },
                    "keywords": {"min": 3, "max": 6},
                }

                guideline = GuidelineRule(
                    journal_id=target_journal_id,
                    source_url="https://publishaid.test/guidelines/ieee-tpami",
                    rules=sample_rules,
                    version=1,
                    is_active=True,
                )
                session.add(guideline)
                print(f"[OK] Created sample guideline rules for journal_id={target_journal_id}.")
            else:
                print("  Guideline rule already exists or no journal found yet.")

            session.commit()
            print("Dev data seeding finished successfully.")
        except Exception as e:
            session.rollback()
            print(f"Error seeding dev data: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    seed_dev_data()

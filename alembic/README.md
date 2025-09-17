Alembic baseline scaffold

This folder contains a minimal Alembic env.py so the project has a starting point for
migrations. To fully use Alembic:

1. Install alembic in your environment: pip install alembic
2. Create an alembic.ini at repo root or copy one from alembic init
3. Configure sqlalchemy.url in alembic.ini or pass it at runtime
4. Run alembic revision --autogenerate -m "baseline"

This scaffold is intentionally minimal to avoid making assumptions about deployment.

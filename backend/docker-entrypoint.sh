#!/bin/sh
set -eu

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

url = os.environ.get(
    "DATABASE_SYNC_URL",
    "postgresql+psycopg2://rakshak:rakshak_dev@db:5432/rakshaklogix",
)
engine = create_engine(url)
last_error = None
for _ in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL is ready")
        break
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        time.sleep(2)
else:
    raise SystemExit(f"PostgreSQL did not become ready: {last_error}")
PY

echo "Applying migrations..."
alembic upgrade head

echo "Loading synthetic logistics data in the background..."
python -m scripts.generate_demo_data --seed "${SYNTHETIC_DATA_SEED:-42}" || echo "Seed skipped"

if [ "${APP_ENV:-development}" = "development" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

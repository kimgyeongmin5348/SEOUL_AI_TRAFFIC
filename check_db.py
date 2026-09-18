import sys
from pathlib import Path

PROJECT_ROOT = Path('.').resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text("SELECT model_version, algorithm, r2_score, top1_accuracy, is_active FROM route_model_versions ORDER BY is_active DESC, trained_at DESC LIMIT 5")).fetchall()
    print("=== Route Model Versions ===")
    for row in result:
        print(row)
finally:
    db.close()

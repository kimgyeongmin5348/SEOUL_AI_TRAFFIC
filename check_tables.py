import sys
from pathlib import Path

PROJECT_ROOT = Path('.').resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from backend.src.db.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
print(db.execute(text("SHOW TABLES")).fetchall())
db.close()

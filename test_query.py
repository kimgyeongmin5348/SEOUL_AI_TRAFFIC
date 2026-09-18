import sys
from pathlib import Path
PROJECT_ROOT = Path('.').resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from backend.src.db.database import SessionLocal
from sqlalchemy import text
from datetime import datetime, timedelta
db = SessionLocal()
res = db.execute(text("""
    SELECT HOUR(s.measured_at) AS hr, AVG(s.speed_kmh) AS avg_spd
    FROM traffic_speed_measurements s
    JOIN traffic_spot_road_maps m ON s.link_id = m.link_id
    WHERE m.spot_id = 'C-03' AND s.measured_at >= :start AND s.speed_kmh > 0
    GROUP BY HOUR(s.measured_at)
"""), {"start": datetime.now() - timedelta(days=30)}).mappings().fetchall()
for row in res:
    print(dict(row))
db.close()

import sys
from pathlib import Path

PROJECT_ROOT = Path('.').resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from sqlalchemy import text
from pyproj import Transformer

TM_TO_WGS84 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
db = SessionLocal()
spot = db.execute(text("SELECT spot_id, spot_name, tm_x, tm_y FROM traffic_spots LIMIT 1")).mappings().first()
lng, lat = TM_TO_WGS84.transform(spot["tm_x"], spot["tm_y"])
print(f"Spot: {spot['spot_name']}, lng: {lng}, lat: {lat}")

lat2 = lat + 0.01
lng2 = lng + 0.01

from backend.src.services.route_training_dataset import fetch_osrm_candidates
origin = {"lat": lat, "lng": lng, "name": "Start"}
dest = {"lat": lat2, "lng": lng2, "name": "End"}
candidates = fetch_osrm_candidates(origin, dest)
if candidates:
    print(f"OSRM candidates found: {len(candidates)}")
    print(f"First candidate distance: {candidates[0]['distance_m']}")
else:
    print("No OSRM candidates")
db.close()

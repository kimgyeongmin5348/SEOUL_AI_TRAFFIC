import asyncio
from datetime import datetime
from backend.src.api.app import predict_route_candidates, RoutePredictionRequest
from backend.src.db.database import SessionLocal

db = SessionLocal()
data = {
  "candidates": [
    {
      "id": "A",
      "duration_sec": 3600,
      "distance_m": 10000,
      "steps": [{"name": "test", "duration_sec": 3600, "distance_m": 10000, "coordinates": []}],
      "coordinates": []
    }
  ],
  "departure_at": datetime.now().isoformat()
}

req = RoutePredictionRequest(**data)
try:
    predict_route_candidates(req, db)
except Exception as e:
    import traceback
    traceback.print_exc()

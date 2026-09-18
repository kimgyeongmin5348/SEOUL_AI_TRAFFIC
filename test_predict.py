import requests, json
from datetime import datetime, timezone

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
  "departure_at": datetime.now(timezone.utc).isoformat()
}

res = requests.post("https://roadpulse-a2sz.onrender.com/api/routes/predict", json=data)
print(res.status_code, res.text)

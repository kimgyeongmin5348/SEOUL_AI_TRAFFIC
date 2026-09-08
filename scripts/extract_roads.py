import urllib.request, json, os

roads_def = [
    {
        "id": "gangbyeon",
        "name": "강변북로",
        "pts": [[126.8620, 37.5685], [127.1480, 37.5750]],
        "defaultSpeed": 23,
    },
    {
        "id": "olympic",
        "name": "올림픽대로",
        "pts": [[126.8050, 37.5880], [127.1560, 37.5580]],
        "defaultSpeed": 38,
    },
    {
        "id": "naebu",
        "name": "내부순환로",
        "pts": [[126.9040, 37.5660], [127.0510, 37.5550]],
        "defaultSpeed": 56,
    },
    {
        "id": "bundang_suseo",
        "name": "분당수서로",
        "pts": [[127.0680, 37.5240], [127.1150, 37.4700]],
        "defaultSpeed": 8,
    },
    {
        "id": "saemunan",
        "name": "새문안로",
        "pts": [[126.9670, 37.5690], [126.9850, 37.5700]],
        "defaultSpeed": 27,
    },
    {
        "id": "yangjae",
        "name": "양재대로",
        "pts": [[127.0390, 37.4680], [127.1000, 37.4880]],
        "defaultSpeed": 44,
    },
    {
        "id": "yeongdong",
        "name": "영동대로",
        "pts": [[127.0580, 37.5280], [127.0700, 37.4950]],
        "defaultSpeed": 31,
    },
    {
        "id": "gyeongbu",
        "name": "경부고속도로",
        "pts": [[127.0180, 37.5180], [127.0390, 37.4680]],
        "defaultSpeed": 65,
    },
    {
        "id": "dongbu",
        "name": "동부간선도로",
        "pts": [[127.0540, 37.6650], [127.0480, 37.5450]],
        "defaultSpeed": 42,
    },
    {
        "id": "seobu",
        "name": "서부간선도로",
        "pts": [[126.8900, 37.5360], [126.8960, 37.4520]],
        "defaultSpeed": 21,
    },
    {
        "id": "teheran",
        "name": "테헤란로",
        "pts": [[127.0276, 37.4979], [127.0632, 37.5088]],
        "defaultSpeed": 24,
    },
]

output_data = []

for r in roads_def:
    start_lng, start_lat = r["pts"][0]
    end_lng, end_lat = r["pts"][1]
    url = f"https://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoadPulse"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode())
            coords = data["routes"][0]["geometry"]["coordinates"]
            lat_lngs = [[round(c[1], 6), round(c[0], 6)] for c in coords]
            output_data.append({
                "id": r["id"],
                "name": r["name"],
                "defaultSpeed": r["defaultSpeed"],
                "coordinates": lat_lngs
            })
            print(f"Done {r['name']}: {len(lat_lngs)} precision points")
    except Exception as e:
        print(f"Error {r['name']}: {e}")

out_file = "frontend/src/data/seoul_roads.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"Successfully saved {len(output_data)} precision roads to {out_file}")

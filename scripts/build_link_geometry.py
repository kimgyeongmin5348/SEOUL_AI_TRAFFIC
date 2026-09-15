"""서울시 서비스링크(road_segments.link_id)의 선형 좌표를 국가 표준노드링크로부터 복원합니다.

입력
- data/external/seoul_standardLink_mapping_info.csv : TOPIS 서비스링크 → 표준링크아이디 (1:N, 순번 없음)
- data/external/MOCT_LINK.{shp,shx,dbf,prj}           : 국가교통정보센터 표준노드링크 (EPSG:5186)
- data/external/raw_road_segments.csv                 : RDS road_segments export (대상 link_id 목록)
- data/external/raw_axis_links.csv                    : 서울시 LinkWithLoad 축·방향·순번 (이웃 링크 사이 빈 구간 보정용)

출력
- data/processed/service_link_geometry.csv       : 서비스링크별 WGS84 폴리라인, 시·종점, 방위, 품질
- data/processed/service_link_standard_links.csv : 서비스링크 → 표준링크 순번 (F_NODE→T_NODE 체인으로 복원)
- data/processed/link_geometry_report.json       : 커버리지·품질 요약

--load-db 를 주면 007 마이그레이션이 적용된 RDS의 road_segments 좌표 컬럼과
service_link_standard_links 테이블을 갱신합니다.
"""
import argparse
import heapq
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import shapefile
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXTERNAL = PROJECT_ROOT / "data" / "external"
PROCESSED = PROJECT_ROOT / "data" / "processed"
GEOMETRY_SOURCE = "moct_link_via_topis_mapping_2026_03"
# 조각 사이 간격이 이 값 이하이면 교차로 통과 구간으로 보고 complete로 판정합니다.
JUNCTION_GAP_M = 100.0
# 같은 서비스링크의 표준링크가 이 거리보다 멀리 떨어져 있으면 매핑 오류(이상치)로 봅니다.
OUTLIER_GAP_M = 500.0
# 빈 구간 최단경로 탐색 상한: max(GAP_FILL_MIN_M, 직선 간격 × GAP_FILL_RATIO)
GAP_FILL_MIN_M = 300.0
GAP_FILL_RATIO = 3.0
# 축 순번상 이웃 링크와의 간격이 이 값을 넘으면 축이 불연속인 것으로 보고 확장하지 않습니다.
AXIS_EXTEND_MAX_M = 1500.0

# 표준노드링크 .prj는 ITRF2000 중부원점(False Northing 600000) = EPSG:5186 입니다.
TO_WGS84 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)

# 같은 서비스링크 안에서 구성 표준링크가 겹칠 때 남길 역할 우선순위입니다.
# 축 확장(head/tail)이 본 체인과 겹치므로 매핑 원본(mapped)을 가장 신뢰합니다.
ROLE_PRIORITY = {"mapped": 0, "gap_fill": 1, "axis_extend": 2, "outlier": 3, "missing": 4}

# 대량 INSERT·좌표 JSON UPDATE는 기본 연결 read timeout(30초)을 넘기므로 청크로 나눠 보냅니다.
DB_CHUNK_ROWS = 1000


def load_mapping(path):
    frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    frame.columns = ["link_id", "standard_link_id"]
    return frame.drop_duplicates()


def _read_link(reader, index):
    record = reader.record(index).as_dict()
    return {
        "f_node": str(record["F_NODE"]),
        "t_node": str(record["T_NODE"]),
        "road_name": record.get("ROAD_NAME") or "",
        "length_m": float(record.get("LENGTH") or 0),
        "points": [tuple(TO_WGS84.transform(x, y)) for x, y in reader.shape(index).points],
    }


def load_standard_links(shapefile_stem, wanted_ids, margin_m=2000.0):
    """매핑된 표준링크와, 빈 구간을 메울 때 쓸 주변(bbox+margin) 표준링크를 읽습니다.

    반환: (매핑 표준링크 dict, 주변 그래프용 표준링크 dict). 전국 156만 건 중 서울 범위만 남깁니다.
    """
    reader = shapefile.Reader(str(shapefile_stem), encoding="cp949")
    index_by_id = {}
    for index, record in enumerate(reader.iterRecords(fields=["LINK_ID"])):
        link_id = str(record[0])
        if link_id in wanted_ids:
            index_by_id[link_id] = index
    xs, ys = [], []
    for index in index_by_id.values():
        bbox = reader.shape(index).bbox
        xs += [bbox[0], bbox[2]]
        ys += [bbox[1], bbox[3]]
    x_min, x_max = min(xs) - margin_m, max(xs) + margin_m
    y_min, y_max = min(ys) - margin_m, max(ys) + margin_m
    mapped, graph = {}, {}
    for index, shape in enumerate(reader.iterShapes()):
        bbox = shape.bbox
        if bbox[2] < x_min or bbox[0] > x_max or bbox[3] < y_min or bbox[1] > y_max:
            continue
        link = _read_link(reader, index)
        link_id = str(reader.record(index, fields=["LINK_ID"])[0])
        graph[link_id] = link
        if link_id in wanted_ids:
            mapped[link_id] = link
    return mapped, graph


def fill_gaps(ordered, standard_links, graph, outgoing=None):
    """연속 표준링크의 T_NODE→F_NODE가 끊긴 곳을 표준노드링크 방향 그래프 최단경로로 메웁니다.

    매핑 파일이 서비스링크 구성 표준링크를 일부만 나열하므로, 끊긴 구간을 실제 도로를 따라 채워야
    OSRM polyline map-match 정확도가 나옵니다. 반환: (채워진 순서 목록, 채움 링크 집합, 남은 최대 간격 m)
    """
    if len(ordered) < 2:
        return list(ordered), set(), 0.0
    outgoing = outgoing if outgoing is not None else outgoing_index(graph)
    filled, inserted, max_gap = [ordered[0]], set(), 0.0
    for previous, current in zip(ordered, ordered[1:]):
        start_node, goal_node = standard_links[previous]["t_node"], standard_links[current]["f_node"]
        if start_node != goal_node:
            gap = _distance_m(standard_links[previous]["points"][-1], standard_links[current]["points"][0])
            path = _shortest_path(outgoing, graph, start_node, goal_node, cutoff_m=max(GAP_FILL_MIN_M, gap * GAP_FILL_RATIO))
            if path:
                filled.extend(path)
                inserted.update(path)
            else:
                max_gap = max(max_gap, gap)
        filled.append(current)
    return filled, inserted, round(max_gap, 1)


def _shortest_path(outgoing, graph, start_node, goal_node, cutoff_m):
    """노드 그래프 Dijkstra. 반환: 경로를 이루는 링크 ID 목록 (없으면 None)."""
    heap, best, via = [(0.0, start_node)], {start_node: 0.0}, {}
    while heap:
        cost, node = heapq.heappop(heap)
        if node == goal_node:
            path = []
            while node in via:
                link_id, node = via[node]
                path.append(link_id)
            return path[::-1]
        if cost > best.get(node, math.inf) or cost > cutoff_m:
            continue
        for link_id in outgoing.get(node, ()):
            link = graph[link_id]
            next_cost = cost + max(link["length_m"], 1.0)
            if next_cost <= cutoff_m and next_cost < best.get(link["t_node"], math.inf):
                best[link["t_node"]] = next_cost
                via[link["t_node"]] = (link_id, node)
                heapq.heappush(heap, (next_cost, link["t_node"]))
    return None


def normalize_road_name(name):
    return re.sub(r"[\s()\[\]·\-_]", "", str(name or ""))


def split_outliers(link_ids, standard_links, db_road_name):
    """끝점 거리 OUTLIER_GAP_M 이내로 이어지는 군집을 만들고, 여러 군집이면 하나만 남깁니다.

    TOPIS 매핑 파일에는 수 km 떨어진 다른 도로의 표준링크가 섞인 행이 있습니다.
    DB road_name과 도로명이 일치하는 군집을 우선하고, 없으면 총연장이 가장 긴 군집을 택합니다.
    반환: (채택 표준링크 목록, 제외 표준링크 목록)
    """
    present = [link_id for link_id in link_ids if link_id in standard_links]
    if len(present) < 2:
        return present, []
    clusters = []
    for link_id in present:
        pts = standard_links[link_id]["points"]
        ends = (pts[0], pts[-1])
        joined = [c for c in clusters if any(_distance_m(a, b) <= OUTLIER_GAP_M for a in ends for member in c for b in (standard_links[member]["points"][0], standard_links[member]["points"][-1]))]
        merged = [link_id] + [m for c in joined for m in c]
        clusters = [c for c in clusters if c not in joined] + [merged]
    if len(clusters) == 1:
        return present, []
    wanted = normalize_road_name(db_road_name)
    def score(cluster):
        names = {normalize_road_name(standard_links[m]["road_name"]) for m in cluster}
        name_match = bool(wanted) and any(wanted in n or n in wanted for n in names if n)
        return (name_match, sum(standard_links[m]["length_m"] for m in cluster))
    keep = max(clusters, key=score)
    kept = [link_id for link_id in present if link_id in keep]
    return kept, [link_id for link_id in present if link_id not in keep]


def chain_standard_links(link_ids, standard_links):
    """표준링크 순서를 복원합니다.

    1) F_NODE→T_NODE 연결로 조각(fragment)을 만든다.
    2) 교차로 내부 연결 링크는 매핑에 없어 노드가 끊기므로, 조각들을 끝점 거리 합이
       최소가 되도록 이어 붙인다.
    반환: (정렬된 표준링크 ID, 조각 사이 최대 간격 m). 표준링크가 하나도 없으면 ([], None).
    """
    present = [link_id for link_id in link_ids if link_id in standard_links]
    if not present:
        return [], None
    by_from = {}
    for link_id in present:
        by_from.setdefault(standard_links[link_id]["f_node"], []).append(link_id)
    to_nodes = {standard_links[link_id]["t_node"] for link_id in present}
    remaining = set(present)
    fragments = []
    while remaining:
        # 체인 시작점: 다른 링크의 T_NODE에서 이어지지 않는 링크. 없으면(순환) 아무 링크나.
        heads = [link_id for link_id in remaining if standard_links[link_id]["f_node"] not in to_nodes]
        current = sorted(heads or remaining)[0]
        fragment = []
        while current in remaining:
            fragment.append(current)
            remaining.discard(current)
            candidates = [n for n in by_from.get(standard_links[current]["t_node"], []) if n in remaining]
            if not candidates:
                break
            current = candidates[0]
        fragments.append(fragment)
    if len(fragments) == 1:
        return fragments[0], 0.0
    best_order, best_gaps = None, None
    for first in range(len(fragments)):
        order, gaps = _greedy_join(fragments, first, standard_links)
        if best_gaps is None or sum(gaps) < sum(best_gaps):
            best_order, best_gaps = order, gaps
    return [link_id for fragment in best_order for link_id in fragment], round(max(best_gaps), 1)


def _greedy_join(fragments, first, standard_links):
    """first 조각에서 시작해 끝점→시작점 거리가 가장 가까운 조각을 차례로 잇습니다."""
    pool = [fragment for index, fragment in enumerate(fragments) if index != first]
    order, gaps = [fragments[first]], []
    while pool:
        tail = standard_links[order[-1][-1]]["points"][-1]
        nearest = min(pool, key=lambda frag: _distance_m(tail, standard_links[frag[0]]["points"][0]))
        gaps.append(_distance_m(tail, standard_links[nearest[0]]["points"][0]))
        pool.remove(nearest)
        order.append(nearest)
    return order, gaps


def _distance_m(a, b):
    lng1, lat1 = a
    lng2, lat2 = b
    x = math.radians(lng2 - lng1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371000 * math.hypot(x, y)


def bearing_deg(start, end):
    lng1, lat1 = map(math.radians, start)
    lng2, lat2 = map(math.radians, end)
    d = lng2 - lng1
    x = math.sin(d) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d)
    return round((math.degrees(math.atan2(x, y)) + 360) % 360, 1)


def outgoing_index(graph):
    outgoing = {}
    for link_id, link in graph.items():
        outgoing.setdefault(link["f_node"], []).append(link_id)
    return outgoing


def extend_along_axis(chains, axis_links, graph):
    """같은 축·방향에서 순번이 이어지는 두 서비스링크 사이의 빈 구간을 메워 양 끝 잘림을 보정합니다.

    TOPIS 매핑은 서비스링크 구성 표준링크를 일부만 주므로 복원 선형이 실제보다 짧습니다.
    이웃 링크 끝→다음 링크 시작 최단경로를 구해 길이 절반씩 앞 링크 뒤·뒤 링크 앞에 붙입니다.
    반환: {link_id: (앞에 붙인 링크, 뒤에 붙인 링크)} — 두 링크의 경계는 근사치이므로 role로 구분합니다.
    """
    outgoing = outgoing_index(graph)
    extensions = {link_id: ([], []) for link_id in chains}
    ordered_axis = axis_links.sort_values("link_sequence")
    for _, group in ordered_axis.groupby(["axis_code", "axis_direction"]):
        ids = [i for i in group["link_id"] if chains.get(i)]
        for previous, current in zip(ids, ids[1:]):
            tail, head = graph[chains[previous][-1]], graph[chains[current][0]]
            if tail["t_node"] == head["f_node"]:
                continue
            gap = _distance_m(tail["points"][-1], head["points"][0])
            if gap <= JUNCTION_GAP_M or gap > AXIS_EXTEND_MAX_M:
                continue
            path = _shortest_path(outgoing, graph, tail["t_node"], head["f_node"], cutoff_m=max(GAP_FILL_MIN_M, gap * GAP_FILL_RATIO))
            if not path:
                continue
            total = sum(graph[i]["length_m"] for i in path)
            cumulative, split = 0.0, len(path)
            for index, link_id in enumerate(path):
                cumulative += graph[link_id]["length_m"]
                if cumulative >= total / 2:
                    split = index + 1
                    break
            extensions[previous][1].extend(path[:split])
            extensions[current][0].extend(path[split:])
    return extensions


def dedupe_sequences(frame):
    """한 서비스링크 안에서 같은 표준링크가 여러 역할로 중복되면 1행만 남깁니다.

    선형 복원에서 축 확장 구간(head/tail)이 본 체인(mapped/gap_fill)과 겹칠 수 있어
    service_link_standard_links PRIMARY(link_id, standard_link_id)를 위반합니다.
    역할 우선순위대로 1행을 남기고 순번을 1..N으로 다시 매깁니다(순서는 유지).
    """
    if frame.empty:
        return frame
    ordered_mask = frame["sequence"].notna()
    ordered = frame[ordered_mask].copy()
    ranked = ordered.assign(
        _rank=ordered["role"].map(ROLE_PRIORITY).fillna(9),
        _seq=ordered["sequence"].astype(float),
    ).sort_values(["link_id", "_rank", "_seq"], kind="stable")
    ranked = ranked.drop_duplicates(subset=["link_id", "standard_link_id"], keep="first")
    ranked = ranked.sort_values(["link_id", "_seq"], kind="stable")
    ranked["sequence"] = ranked.groupby("link_id").cumcount() + 1
    ranked = ranked.drop(columns=["_rank", "_seq"])
    used = set(zip(ranked["link_id"], ranked["standard_link_id"]))
    others = frame[~ordered_mask].copy()
    others = others[[key not in used for key in zip(others["link_id"], others["standard_link_id"])]]
    others["_rank"] = others["role"].map(ROLE_PRIORITY).fillna(9)
    others = others.sort_values(["link_id", "_rank"], kind="stable")
    others = others.drop_duplicates(subset=["link_id", "standard_link_id"], keep="first")
    others = others.drop(columns=["_rank"])
    return pd.concat([ranked, others], ignore_index=True)


def build_geometry(mapping, standard_links, graph, road_names, axis_links=None):
    """road_names: {link_id: DB road_name}. 대상 서비스링크는 이 dict의 키입니다."""
    grouped = mapping.groupby("link_id")["standard_link_id"].apply(list)
    outgoing = outgoing_index(graph)
    chains, meta = {}, {}
    for link_id in sorted(road_names):
        std_ids = grouped.get(link_id, [])
        kept, outliers = split_outliers(std_ids, standard_links, road_names[link_id])
        mapped_order, _ = chain_standard_links(kept, standard_links)
        ordered, gap_filled, max_gap_m = fill_gaps(mapped_order, standard_links, graph, outgoing)
        chains[link_id] = ordered
        meta[link_id] = {"std_ids": std_ids, "mapped_order": mapped_order, "gap_filled": gap_filled,
                         "outliers": outliers, "missing": [s for s in std_ids if s not in standard_links],
                         "max_gap_m": max_gap_m}
    extensions = extend_along_axis(chains, axis_links, graph) if axis_links is not None else {}

    rows, sequences = [], []
    for link_id, ordered in chains.items():
        info = meta[link_id]
        head, tail = extensions.get(link_id, ([], []))
        final = head + ordered + tail
        roles = {**{s: "mapped" for s in ordered}, **{s: "gap_fill" for s in info["gap_filled"]},
                 **{s: "axis_extend" for s in head + tail}}
        for sequence, std_id in enumerate(final, start=1):
            sequences.append({"link_id": link_id, "standard_link_id": std_id, "sequence": sequence,
                              "in_moct_link": True, "role": roles[std_id]})
        for std_id in info["outliers"]:
            sequences.append({"link_id": link_id, "standard_link_id": std_id, "sequence": None,
                              "in_moct_link": True, "role": "outlier"})
        for std_id in info["missing"]:
            sequences.append({"link_id": link_id, "standard_link_id": std_id, "sequence": None,
                              "in_moct_link": False, "role": "missing"})
        points = []
        for std_id in final:
            for point in graph[std_id]["points"]:
                if not points or points[-1] != point:
                    points.append(point)
        # 교차로 내부 연결 링크가 매핑에 없어 생기는 짧은 간격은 정상으로 봅니다.
        if not info["std_ids"]:
            quality = "unmapped"
        elif not points:
            quality = "missing"
        elif info["missing"] or info["max_gap_m"] > JUNCTION_GAP_M:
            quality = "partial"
        else:
            quality = "complete"
        rows.append({
            "link_id": link_id,
            "standard_link_count": len(info["std_ids"]),
            "standard_link_matched": len(info["mapped_order"]),
            "standard_link_gap_filled": len(info["gap_filled"]),
            "standard_link_outliers": len(info["outliers"]),
            "max_gap_m": info["max_gap_m"],
            "extended_head_m": round(sum(graph[s]["length_m"] for s in head), 1),
            "extended_tail_m": round(sum(graph[s]["length_m"] for s in tail), 1),
            "geometry_quality": quality,
            "start_lng": points[0][0] if points else None,
            "start_lat": points[0][1] if points else None,
            "end_lng": points[-1][0] if points else None,
            "end_lat": points[-1][1] if points else None,
            "bearing_deg": bearing_deg(points[0], points[-1]) if len(points) > 1 else None,
            "length_m": round(sum(graph[s]["length_m"] for s in final), 1) if final else None,
            "moct_road_names": "|".join(dict.fromkeys(graph[s]["road_name"] for s in final)),
            "geometry_json": json.dumps([[round(lng, 7), round(lat, 7)] for lng, lat in points]) if points else None,
        })
    return pd.DataFrame(rows), dedupe_sequences(pd.DataFrame(sequences))


def load_to_db(geometry, sequences):
    from sqlalchemy import create_engine, text
    from backend.src.core.config import settings

    # 공유 engine은 read timeout이 30초라 5천여 건 좌표 JSON UPDATE에서 연결이 끊깁니다.
    # 전용 engine과 청크를 써서 읽기/쓰기 여유를 주고, 끝나면 연결을 정리합니다.
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10, "read_timeout": 600, "write_timeout": 600, "charset": "utf8mb4"},
    )
    delete_links = text("DELETE FROM service_link_standard_links")
    insert_link = text("""
        INSERT INTO service_link_standard_links (link_id, standard_link_id, sequence, in_moct_link, role)
        VALUES (:link_id, :standard_link_id, :sequence, :in_moct_link, :role)
    """)
    update_geometry = text("""
        UPDATE road_segments SET
            start_lat = :start_lat, start_lng = :start_lng, end_lat = :end_lat, end_lng = :end_lng,
            bearing_deg = :bearing_deg, geometry_length_m = :length_m, geometry_json = :geometry_json,
            geometry_source = :geometry_source, geometry_quality = :geometry_quality,
            geometry_extended_head_m = :extended_head_m, geometry_extended_tail_m = :extended_tail_m
        WHERE link_id = :link_id
    """)
    sequence_rows = sequences.astype(object).where(sequences.notna(), None).to_dict("records")
    rows = geometry.astype(object).where(geometry.notna(), None).to_dict("records")
    geometry_rows = [{**row, "geometry_source": GEOMETRY_SOURCE if row["geometry_json"] else None} for row in rows]
    try:
        with engine.begin() as connection:
            connection.execute(delete_links)
            for start in range(0, len(sequence_rows), DB_CHUNK_ROWS):
                connection.execute(insert_link, sequence_rows[start:start + DB_CHUNK_ROWS])
            for start in range(0, len(geometry_rows), DB_CHUNK_ROWS):
                connection.execute(update_geometry, geometry_rows[start:start + DB_CHUNK_ROWS])
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Build service link geometry from MOCT standard links")
    parser.add_argument("--mapping", type=Path, default=EXTERNAL / "seoul_standardLink_mapping_info.csv")
    parser.add_argument("--moct-link", type=Path, default=EXTERNAL / "MOCT_LINK")
    parser.add_argument("--road-segments", type=Path, default=EXTERNAL / "raw_road_segments.csv")
    parser.add_argument("--axis-links", type=Path, default=EXTERNAL / "raw_axis_links.csv")
    parser.add_argument("--load-db", action="store_true", help="RDS road_segments·service_link_standard_links 갱신")
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    segments = pd.read_csv(args.road_segments, dtype=str, encoding="utf-8-sig")
    road_names = dict(zip(segments["link_id"], segments["road_name"].fillna("")))
    target_links = set(road_names)
    standard_links, graph = load_standard_links(args.moct_link, set(mapping["standard_link_id"]))
    axis_links = None
    if args.axis_links.is_file():
        axis_links = pd.read_csv(args.axis_links, dtype=str)
        axis_links["link_sequence"] = pd.to_numeric(axis_links["link_sequence"], errors="coerce")
    geometry, sequences = build_geometry(mapping, standard_links, graph, road_names, axis_links)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    geometry.to_csv(PROCESSED / "service_link_geometry.csv", index=False, encoding="utf-8-sig")
    sequences.to_csv(PROCESSED / "service_link_standard_links.csv", index=False, encoding="utf-8-sig")
    report = {
        "geometry_source": GEOMETRY_SOURCE,
        "road_segments": len(target_links),
        "mapped_service_links": int(mapping["link_id"].isin(target_links).groupby(mapping["link_id"]).any().sum()),
        "standard_links_in_mapping": int(mapping["standard_link_id"].nunique()),
        "standard_links_found_in_moct": len(standard_links),
        "quality_counts": dict(Counter(geometry["geometry_quality"])),
        "graph_links_loaded": len(graph),
        "service_links_gap_filled": int((geometry["standard_link_gap_filled"] > 0).sum()),
        "gap_fill_standard_links": int(geometry["standard_link_gap_filled"].sum()),
        "service_links_axis_extended": int(((geometry["extended_head_m"] > 0) | (geometry["extended_tail_m"] > 0)).sum()),
        "axis_extended_total_m": float(round((geometry["extended_head_m"] + geometry["extended_tail_m"]).sum(), 1)),
        "service_links_with_outliers": int((geometry["standard_link_outliers"] > 0).sum()),
        "outlier_standard_links": int(geometry["standard_link_outliers"].sum()),
        "max_gap_m_percentiles": {p: float(round(geometry["max_gap_m"].quantile(float(p)), 1))
                                  for p in ("0.5", "0.9", "0.95", "0.99", "1.0")},
    }
    (PROCESSED / "link_geometry_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.load_db:
        load_to_db(geometry, sequences)
        print("RDS road_segments / service_link_standard_links updated.")


if __name__ == "__main__":
    main()

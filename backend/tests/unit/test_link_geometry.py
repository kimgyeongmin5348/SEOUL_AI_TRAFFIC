import json

import pandas as pd

from scripts.build_link_geometry import (
    build_geometry,
    chain_standard_links,
    dedupe_sequences,
    extend_along_axis,
    fill_gaps,
    split_outliers,
)

# 경도 0.001° ≈ 88m (위도 37.5°). 동쪽으로 뻗은 직선 도로를 표준링크로 잘라 만든 합성 그래프.
LAT = 37.5


def link(f_node, t_node, x0, x1, road_name="테스트로", length_m=None):
    return {"f_node": f_node, "t_node": t_node, "road_name": road_name,
            "length_m": length_m if length_m is not None else abs(x1 - x0) * 88000,
            "points": [(x0, LAT), (x1, LAT)]}


def graph():
    # n0 -a- n1 -b- n2 -c- n3 -d- n4 -e- n5 (연속), z는 5km 떨어진 다른 도로
    return {
        "a": link("n0", "n1", 127.000, 127.001),
        "b": link("n1", "n2", 127.001, 127.002),
        "c": link("n2", "n3", 127.002, 127.003),
        "d": link("n3", "n4", 127.003, 127.004),
        "e": link("n4", "n5", 127.004, 127.005),
        "z": link("z0", "z1", 127.060, 127.061, road_name="딴길"),
    }


def test_chain_orders_by_nodes_and_joins_broken_fragments_by_distance():
    g = graph()
    ordered, max_gap = chain_standard_links(["c", "a", "b"], g)
    assert ordered == ["a", "b", "c"] and max_gap == 0.0
    # 교차로 링크 b가 매핑에 없으면 노드 체인이 끊기지만 끝점 거리로 a→c 순서를 복원한다.
    ordered, max_gap = chain_standard_links(["c", "a"], g)
    assert ordered == ["a", "c"] and 80 < max_gap < 100


def test_split_outliers_drops_far_cluster_and_prefers_db_road_name():
    g = graph()
    kept, outliers = split_outliers(["a", "b", "z"], g, "테스트로")
    assert kept == ["a", "b"] and outliers == ["z"]
    # DB 도로명이 떨어진 쪽과 일치하면 그쪽을 남긴다.
    kept, outliers = split_outliers(["a", "b", "z"], g, "딴길")
    assert kept == ["z"] and set(outliers) == {"a", "b"}


def test_fill_gaps_inserts_shortest_path_links_between_mapped_links():
    g = graph()
    filled, inserted, max_gap = fill_gaps(["a", "d"], g, g)
    assert filled == ["a", "b", "c", "d"] and inserted == {"b", "c"} and max_gap == 0.0


def test_axis_extension_splits_gap_between_neighbouring_service_links():
    g = graph()
    chains = {"S1": ["a"], "S2": ["e"]}
    axis = pd.DataFrame([{"axis_code": "1", "axis_direction": "상행", "link_sequence": 1, "link_id": "S1"},
                         {"axis_code": "1", "axis_direction": "상행", "link_sequence": 2, "link_id": "S2"}])
    extensions = extend_along_axis(chains, axis, g)
    # b, c, d(각 88m) 중 절반(≥132m)까지 앞 링크 뒤에, 나머지는 뒤 링크 앞에 붙는다.
    assert extensions["S1"] == ([], ["b", "c"])
    assert extensions["S2"] == (["d"], [])


def test_dedupe_sequences_prefers_ordered_row_over_outlier_collision():
    # gap_fill 최단경로가 outlier로 제외한 표준링크를 지나면 순번 행과 outlier 행이 겹친다.
    # 실제 선형에 포함된 순번 있는 행을 남기고, PRIMARY(link_id, standard_link_id)를 지킨다.
    frame = pd.DataFrame([
        {"link_id": "S1", "standard_link_id": "a", "sequence": 1, "in_moct_link": True, "role": "mapped"},
        {"link_id": "S1", "standard_link_id": "a", "sequence": None, "in_moct_link": True, "role": "outlier"},
        {"link_id": "S1", "standard_link_id": "b", "sequence": 2, "in_moct_link": True, "role": "gap_fill"},
    ])
    result = dedupe_sequences(frame)
    assert not result.duplicated(subset=["link_id", "standard_link_id"]).any()
    row = result.set_index("standard_link_id")
    assert row.loc["a", "role"] == "mapped" and row.loc["a", "sequence"] == 1
    assert list(result[result.link_id == "S1"]["sequence"]) == [1, 2]


def test_build_geometry_reports_quality_and_wgs84_polyline():
    g = graph()
    mapping = pd.DataFrame([("S1", "a"), ("S1", "c"), ("S1", "z"), ("S2", "e"), ("S3", "ghost")],
                           columns=["link_id", "standard_link_id"])
    standard = {k: v for k, v in g.items() if k in {"a", "c", "z", "e"}}
    geometry, sequences = build_geometry(mapping, standard, g, {"S1": "테스트로", "S2": "테스트로", "S3": "테스트로", "S4": ""})
    rows = geometry.set_index("link_id")
    assert rows.loc["S1", "geometry_quality"] == "complete"
    assert rows.loc["S1", "standard_link_outliers"] == 1 and rows.loc["S1", "standard_link_gap_filled"] == 1
    assert json.loads(rows.loc["S1", "geometry_json"]) == [[127.0, LAT], [127.001, LAT], [127.002, LAT], [127.003, LAT]]
    assert 85 < rows.loc["S1", "bearing_deg"] < 95  # 동쪽
    assert rows.loc["S3", "geometry_quality"] == "missing" and rows.loc["S4", "geometry_quality"] == "unmapped"
    roles = sequences[sequences.link_id == "S1"].set_index("standard_link_id")["role"].to_dict()
    assert roles == {"a": "mapped", "b": "gap_fill", "c": "mapped", "z": "outlier"}
    assert sequences[sequences.link_id == "S3"].iloc[0]["role"] == "missing"

from unittest.mock import MagicMock, call, patch

from backend.src.services.collector_service import DataCollectorService
from backend.src.services.seoul_client import SeoulOpenApiClient


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


def xml(service: str, rows: str) -> str:
    return (
        f"<{service}><list_total_count>1</list_total_count>"
        "<RESULT><CODE>INFO-000</CODE><MESSAGE>OK</MESSAGE></RESULT>"
        f"{rows}</{service}>"
    )


def test_client_discovers_links_through_official_master_apis():
    responses = [
        FakeResponse(xml("RoadDivInfo", "<row><road_div_cd>02</road_div_cd><road_div_nm>도시고속도로</road_div_nm></row>")),
        FakeResponse(xml("RoadInfo", "<row><road_div_cd>02</road_div_cd><axis_cd>204</axis_cd><axis_name>분당수서로</axis_name></row>")),
        FakeResponse(xml("LinkWithLoad", "<row><axis_cd>204</axis_cd><axis_dir>상행</axis_dir><link_seq>1</link_seq><link_id>1220005000</link_id></row>")),
    ]
    client = SeoulOpenApiClient(traffic_api_key="test", incident_api_key="test")

    with patch("backend.src.services.seoul_client.httpx.get", side_effect=responses) as get:
        divisions = client.get_road_divisions()
        axes = client.get_road_axes(divisions[0]["road_div_code"])
        links = client.get_road_links(axes[0]["axis_code"])

    assert links == [{
        "axis_code": "204", "axis_direction": "상행",
        "link_sequence": "1", "link_id": "1220005000",
    }]
    assert "/RoadDivInfo/1/1000/" in get.call_args_list[0].args[0]
    assert "/RoadInfo/1/1000/02/" in get.call_args_list[1].args[0]
    assert "/LinkWithLoad/1/1000/204/" in get.call_args_list[2].args[0]


def test_speed_sync_uses_every_registered_link_instead_of_five_defaults():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        ("1000000100",),
        ("1210000500",),
        ("1220003800",),
    ]
    seoul = MagicMock()
    seoul.get_traffic_speed.side_effect = lambda link_id: {
        "link_id": link_id,
        "measured_at": "2026-09-11 12:00:00",
        "speed_kmh": 30.0,
        "travel_time_sec": 60,
    }
    collector = DataCollectorService(db, seoul_client=seoul, kma_client=MagicMock())

    assert collector.sync_traffic_speed() == 3
    assert sorted(seoul.get_traffic_speed.call_args_list, key=str) == sorted([
        call("1000000100"), call("1210000500"), call("1220003800")
    ], key=str)
    db.commit.assert_called_once()


def test_road_segment_sync_deduplicates_links_shared_by_axes():
    db = MagicMock()
    seoul = MagicMock()
    seoul.get_road_divisions.return_value = [
        {"road_div_code": "02", "road_div_name": "도시고속도로"}
    ]
    seoul.get_road_axes.return_value = [
        {"road_div_code": "02", "axis_code": "204", "axis_name": "A"},
        {"road_div_code": "02", "axis_code": "205", "axis_name": "B"},
    ]
    seoul.get_road_links.side_effect = [
        [{"axis_code": "204", "axis_direction": "상행", "link_sequence": "1", "link_id": "L1"}],
        [
            {"axis_code": "205", "axis_direction": "하행", "link_sequence": "1", "link_id": "L1"},
            {"axis_code": "205", "axis_direction": "하행", "link_sequence": "2", "link_id": "L2"},
        ],
    ]
    collector = DataCollectorService(db, seoul_client=seoul, kma_client=MagicMock())

    assert collector.sync_road_segments() == 2
    assert db.execute.call_count == 2
    db.commit.assert_called_once()


def test_speed_sync_auto_bootstraps_road_segments_if_empty():
    db = MagicMock()
    # 첫 조회 시 빈 목록 반환 -> sync_road_segments 호출 후 두 번째 조회에서 링크 반환
    db.execute.return_value.fetchall.side_effect = [
        [],
        [("1000000100",)],
    ]
    seoul = MagicMock()
    seoul.get_traffic_speed.return_value = {
        "link_id": "1000000100",
        "measured_at": "2026-09-11 12:00:00",
        "speed_kmh": 45.0,
        "travel_time_sec": 30,
    }
    collector = DataCollectorService(db, seoul_client=seoul, kma_client=MagicMock())
    with patch.object(collector, "sync_road_segments") as mock_sync_road:
        count = collector.sync_traffic_speed()
        mock_sync_road.assert_called_once()
        assert count == 1


def test_speed_sync_handles_explicit_links_with_deduplication():
    db = MagicMock()
    seoul = MagicMock()
    seoul.get_traffic_speed.return_value = {
        "link_id": "1000000100",
        "measured_at": "2026-09-11 12:00:00",
        "speed_kmh": 45.0,
        "travel_time_sec": 30,
    }
    collector = DataCollectorService(db, seoul_client=seoul, kma_client=MagicMock())
    with patch.object(collector, "ensure_road_segment") as mock_ensure:
        count = collector.sync_traffic_speed(link_ids=["1000000100", "1000000100"])
        # ensure_road_segment는 명시적 인자 순회 시 호출
        assert mock_ensure.call_count == 2
        # dict.fromkeys()로 중복 제거되어 실제 speed API는 1회만 호출
        assert seoul.get_traffic_speed.call_count == 1
        assert count == 1


def test_speed_sync_continues_on_single_link_failure():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        ("link_ok",),
        ("link_fail",),
    ]
    seoul = MagicMock()

    def fake_get_speed(link_id: str):
        if link_id == "link_fail":
            raise RuntimeError("API connection timeout")
        return {
            "link_id": link_id,
            "measured_at": "2026-09-11 12:00:00",
            "speed_kmh": 50.0,
            "travel_time_sec": 40,
        }

    seoul.get_traffic_speed.side_effect = fake_get_speed
    collector = DataCollectorService(db, seoul_client=seoul, kma_client=MagicMock())

    assert collector.sync_traffic_speed() == 1
    db.commit.assert_called_once()


def test_get_traffic_speed_handles_empty_or_malformed_xml():
    client = SeoulOpenApiClient(traffic_api_key="test", incident_api_key="test")
    fake_xml = xml("TrafficInfo", "<row><link_id>1000000100</link_id><prcs_spd></prcs_spd><prcs_trv_time></prcs_trv_time></row>")
    with patch("backend.src.services.seoul_client.httpx.get", return_value=FakeResponse(fake_xml)):
        result = client.get_traffic_speed("1000000100")
        assert result is not None
        assert result["link_id"] == "1000000100"
        assert result["speed_kmh"] == 0.0
        assert result["travel_time_sec"] == 0


from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.src.api.app import app, get_db, serialize
from backend.src.services.collector_service import DataCollectorService


def test_health_check_does_not_require_database():
    result = TestClient(app).get('/api/health')
    assert result.status_code == 200
    assert result.json() == {'status': 'ok'}


def test_observations_and_db_collection_timestamps_have_distinct_timezones():
    stamp = datetime(2026, 9, 8, 1, 4)
    assert serialize(stamp).endswith('+09:00')
    assert serialize(stamp, timezone.utc).endswith('+00:00')


def test_empty_and_unavailable_database_are_distinct():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        db.execute.return_value.scalar.return_value = None
        result = client.get('/api/data/prediction')
        assert result.status_code == 200
        assert result.json()['rows'] == []
        assert result.json()['latest_at'] is None
        db.execute.side_effect = OperationalError('query', {}, Exception('secret'))
        result = client.get('/api/data/weather')
        assert result.status_code == 503
        assert 'secret' not in result.text
        assert client.get('/api/data/unknown').status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_weather_defaults_to_previous_korean_day_at_month_boundary():
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 1, 0, 15, tzinfo=tz)

    db, kma = MagicMock(), MagicMock()
    kma.get_weather_stations.return_value = []
    kma.get_hourly_weather.return_value = []
    collector = DataCollectorService(db, seoul_client=MagicMock(), kma_client=kma)
    with patch('backend.src.services.collector_service.datetime', Clock):
        assert collector.sync_weather_measurements() == 0
    kma.get_hourly_weather.assert_called_once_with(
        station_id='108', start_date='20260831', start_hour='00',
        end_date='20260831', end_hour='23',
    )

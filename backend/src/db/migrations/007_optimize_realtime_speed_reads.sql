-- 최근 시간 범위에서 링크별 최신 속도를 조회하는 대시보드 쿼리를 가속합니다.
-- link_id 선두의 기존 UNIQUE 인덱스는 measured_at 범위 검색에 적합하지 않습니다.

CREATE INDEX idx_speed_measured_link
    ON traffic_speed_measurements (measured_at, link_id);

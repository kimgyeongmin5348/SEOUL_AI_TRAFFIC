-- OSRM step을 링크 기하에 map-match한 결과를 후보 경로 로그에 남깁니다.
-- 방향 매칭은 axis_direction(상/하행)이 아니라 링크 bearing_deg와 step 진행 방위를 직접 비교합니다.
-- 링크 기하가 없는 환경에서는 모든 값이 NULL이고 방향 매칭은 '미적용'으로 남습니다.

ALTER TABLE route_request_candidates
    ADD COLUMN link_match_ratio DOUBLE NULL AFTER speed_match_ratio,
    ADD COLUMN direction_match_ratio DOUBLE NULL AFTER link_match_ratio,
    ADD COLUMN direction_matched_steps INT NULL AFTER direction_match_ratio,
    ADD COLUMN link_match_json JSON NULL AFTER coordinates_json;
-- road_segments 테이블에 도로 축 코드, 주행 방향(상행/하행), 링크 순번 컬럼을 추가합니다.
-- 서울시 LinkWithLoad 원천 API의 axis_cd, axis_dir, link_seq와 대응됩니다.

ALTER TABLE road_segments
    ADD COLUMN axis_code VARCHAR(20) NULL AFTER region_code,
    ADD COLUMN axis_direction VARCHAR(20) NULL AFTER axis_code,
    ADD COLUMN link_sequence INT NULL AFTER axis_direction;


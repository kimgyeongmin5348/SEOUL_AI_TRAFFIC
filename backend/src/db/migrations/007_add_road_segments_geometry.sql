-- road_segments에 서비스링크 선형(WGS84)을 추가하고, 서비스링크→표준노드링크 구성 순번 테이블을 만듭니다.
-- 선형은 TOPIS 서비스링크-표준링크 매핑(2026-03)과 국가 표준노드링크(MOCT_LINK)로 복원합니다.
-- (scripts/build_link_geometry.py --load-db)

ALTER TABLE road_segments
    ADD COLUMN start_lat DECIMAL(10, 7) NULL AFTER link_sequence,
    ADD COLUMN start_lng DECIMAL(10, 7) NULL AFTER start_lat,
    ADD COLUMN end_lat DECIMAL(10, 7) NULL AFTER start_lng,
    ADD COLUMN end_lng DECIMAL(10, 7) NULL AFTER end_lat,
    ADD COLUMN bearing_deg DECIMAL(5, 1) NULL AFTER end_lng,
    ADD COLUMN geometry_length_m DOUBLE NULL AFTER bearing_deg,
    ADD COLUMN geometry_json JSON NULL AFTER geometry_length_m,
    ADD COLUMN geometry_source VARCHAR(50) NULL AFTER geometry_json,
    ADD COLUMN geometry_quality VARCHAR(20) NULL AFTER geometry_source,
    ADD COLUMN geometry_extended_head_m DOUBLE NULL AFTER geometry_quality,
    ADD COLUMN geometry_extended_tail_m DOUBLE NULL AFTER geometry_extended_head_m;

-- role: mapped(매핑 파일 수록) / gap_fill(매핑 링크 사이 최단경로 보충) / axis_extend(축 이웃 링크 사이 보충, 경계는 근사)
--       / outlier(매핑 오류로 제외) / missing(표준노드링크에 없음)
CREATE TABLE IF NOT EXISTS service_link_standard_links (
    link_id VARCHAR(20) NOT NULL,
    standard_link_id VARCHAR(20) NOT NULL,
    sequence INT NULL,
    in_moct_link BOOLEAN NOT NULL DEFAULT TRUE,
    role VARCHAR(20) NOT NULL,
    PRIMARY KEY (link_id, standard_link_id),
    INDEX ix_service_link_standard_link (standard_link_id),
    CONSTRAINT fk_service_link_standard_link
        FOREIGN KEY (link_id) REFERENCES road_segments (link_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

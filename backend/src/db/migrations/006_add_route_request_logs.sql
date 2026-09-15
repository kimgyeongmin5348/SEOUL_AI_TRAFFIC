-- /api/routes/predict 요청과 OSRM 후보 경로를 저장해 경로 단위 학습 데이터셋을 축적합니다.
-- route_requests: 요청 1건 = 1행 (route_request_id 단위로 후보 간 순위·최적 경로를 평가)
-- route_request_candidates: 후보 경로 1개 = 1행 (actual_duration_sec는 이후 링크 관측으로 재구성해 채움)

CREATE TABLE IF NOT EXISTS route_requests (
    route_request_id CHAR(36) NOT NULL,
    requested_at DATETIME NOT NULL,
    departure_at DATETIME NOT NULL,
    target_at DATETIME NULL,
    origin_name VARCHAR(200) NULL,
    origin_lat DECIMAL(10, 6) NULL,
    origin_lng DECIMAL(10, 6) NULL,
    destination_name VARCHAR(200) NULL,
    destination_lat DECIMAL(10, 6) NULL,
    destination_lng DECIMAL(10, 6) NULL,
    candidate_count TINYINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    status_message VARCHAR(500) NULL,
    model_version VARCHAR(50) NULL,
    ai_available BOOLEAN NOT NULL DEFAULT FALSE,
    ai_selected_route_id VARCHAR(20) NULL,
    osrm_default_route_id VARCHAR(20) NULL,
    traffic_observed_at DATETIME NULL,
    weather_observed_at DATETIME NULL,
    forecast_steps TINYINT NULL,
    PRIMARY KEY (route_request_id),
    INDEX ix_route_request_requested_at (requested_at),
    INDEX ix_route_request_departure_at (departure_at)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS route_request_candidates (
    id BIGINT NOT NULL AUTO_INCREMENT,
    route_request_id CHAR(36) NOT NULL,
    route_id VARCHAR(20) NOT NULL,
    route_distance_m DOUBLE NULL,
    osrm_duration_sec DOUBLE NOT NULL,
    segment_count INT NOT NULL,
    route_direction_code TINYINT NULL,
    score DOUBLE NULL,
    traffic_penalty_sec DOUBLE NULL,
    incident_penalty_sec DOUBLE NULL,
    speed_penalty_sec DOUBLE NULL,
    coverage DOUBLE NULL,
    match_ratio DOUBLE NULL,
    speed_match_ratio DOUBLE NULL,
    incident_count INT NULL,
    predicted_volume DOUBLE NULL,
    typical_volume DOUBLE NULL,
    ai_selected BOOLEAN NOT NULL DEFAULT FALSE,
    steps_json JSON NOT NULL,
    coordinates_json JSON NULL,
    actual_duration_sec DOUBLE NULL,
    actual_duration_quality VARCHAR(20) NULL,
    actual_duration_computed_at DATETIME NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_route_request_candidate UNIQUE (route_request_id, route_id),
    CONSTRAINT fk_route_request_candidate_request
        FOREIGN KEY (route_request_id) REFERENCES route_requests (route_request_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

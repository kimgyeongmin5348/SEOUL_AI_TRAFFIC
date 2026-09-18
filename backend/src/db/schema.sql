-- RoadPulse MySQL schema
-- 실행 대상: AWS RDS의 roadpulse 데이터베이스
-- 여러 번 실행해도 기존 테이블과 데이터는 삭제하지 않습니다.

SET NAMES utf8mb4;

-- 로그인 사용자와 서버측 세션
CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL AUTO_INCREMENT,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash CHAR(64) NOT NULL,
    user_id BIGINT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (token_hash),
    KEY ix_user_sessions_user (user_id),
    KEY ix_user_sessions_expires (expires_at),
    CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS favorite_routes (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    origin VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    label VARCHAR(255) NULL,
    search_count INT NOT NULL DEFAULT 1,
    avg_time_min INT NULL,
    current_time_min INT NULL,
    last_searched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_favorite_route_user_path (user_id, origin, destination),
    KEY ix_favorite_routes_user_rank (user_id, search_count, last_searched_at),
    CONSTRAINT fk_favorite_routes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 서울시 SpotInfo 기준정보
CREATE TABLE IF NOT EXISTS traffic_spots (
    spot_id VARCHAR(20) NOT NULL,
    spot_name VARCHAR(150) NOT NULL,
    tm_x DECIMAL(12, 6) NOT NULL,
    tm_y DECIMAL(12, 6) NOT NULL,
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (spot_id)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 LinkInfo 도로 구간 기준정보
CREATE TABLE IF NOT EXISTS road_segments (
    link_id VARCHAR(20) NOT NULL,
    road_name VARCHAR(150) NULL,
    start_node_name VARCHAR(150) NULL,
    end_node_name VARCHAR(150) NULL,
    length_m INT NULL,
    region_code VARCHAR(20) NULL,
    axis_code VARCHAR(20) NULL,
    axis_direction VARCHAR(20) NULL,
    link_sequence INT NULL,
    -- 서비스링크 선형(WGS84). scripts/build_link_geometry.py 로 표준노드링크에서 복원
    start_lat DECIMAL(10, 7) NULL,
    start_lng DECIMAL(10, 7) NULL,
    end_lat DECIMAL(10, 7) NULL,
    end_lng DECIMAL(10, 7) NULL,
    bearing_deg DECIMAL(5, 1) NULL,
    geometry_length_m DOUBLE NULL,
    geometry_json JSON NULL,
    geometry_source VARCHAR(50) NULL,
    geometry_quality VARCHAR(20) NULL,
    geometry_extended_head_m DOUBLE NULL,
    geometry_extended_tail_m DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (link_id)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 기상청 ASOS 관측소 기준정보
CREATE TABLE IF NOT EXISTS weather_stations (
    weather_station_id VARCHAR(10) NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 7) NULL,
    longitude DECIMAL(10, 7) NULL,
    elevation_m DECIMAL(8, 2) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (weather_station_id)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

  COLLATE = utf8mb4_unicode_ci;

-- 교통량 측정지점과 도로 링크 간 공간 매핑
CREATE TABLE IF NOT EXISTS traffic_spot_road_maps (
    spot_id VARCHAR(20) NOT NULL,
    link_id VARCHAR(20) NOT NULL,
    match_distance_m DECIMAL(8, 2) NOT NULL,
    match_method VARCHAR(30) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (spot_id, link_id),
    CONSTRAINT fk_spot_road_map_spot
        FOREIGN KEY (spot_id) REFERENCES traffic_spots (spot_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_spot_road_map_link
        FOREIGN KEY (link_id) REFERENCES road_segments (link_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 VolInfo 교통량 측정값
CREATE TABLE IF NOT EXISTS traffic_volume_measurements (
    id BIGINT NOT NULL AUTO_INCREMENT,
    spot_id VARCHAR(20) NOT NULL,
    measured_at DATETIME NOT NULL,
    direction_code TINYINT NOT NULL,
    lane_no SMALLINT NOT NULL,
    traffic_volume INT NOT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, measured_at),
    CONSTRAINT uq_volume_spot_time_direction_lane
        UNIQUE (spot_id, measured_at, direction_code, lane_no),
    CONSTRAINT fk_volume_spot
        FOREIGN KEY (spot_id) REFERENCES traffic_spots (spot_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 TrafficInfo 도로 구간별 속도 측정값
CREATE TABLE IF NOT EXISTS traffic_speed_measurements (
    id BIGINT NOT NULL AUTO_INCREMENT,
    link_id VARCHAR(20) NOT NULL,
    measured_at DATETIME NOT NULL,
    speed_kmh DECIMAL(6, 2) NOT NULL,
    travel_time_sec INT NOT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_speed_measured_link (measured_at, link_id),
    CONSTRAINT uq_speed_link_measured_at
        UNIQUE (link_id, measured_at),
    CONSTRAINT fk_speed_link
        FOREIGN KEY (link_id) REFERENCES road_segments (link_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 기상청 ASOS 시간별 관측값
CREATE TABLE IF NOT EXISTS weather_measurements (
    id BIGINT NOT NULL AUTO_INCREMENT,
    weather_station_id VARCHAR(10) NOT NULL,
    observed_at DATETIME NOT NULL,
    temperature_c DECIMAL(5, 2) NULL,
    rainfall_mm DECIMAL(7, 2) NULL,
    humidity_pct DECIMAL(5, 2) NULL,
    wind_speed_ms DECIMAL(6, 2) NULL,
    wind_direction_deg SMALLINT NULL,
    pressure_hpa DECIMAL(7, 2) NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_weather_station_observed_at
        UNIQUE (weather_station_id, observed_at),
    CONSTRAINT fk_weather_measurement_station
        FOREIGN KEY (weather_station_id)
        REFERENCES weather_stations (weather_station_id)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 AccInfo 돌발상황
CREATE TABLE IF NOT EXISTS incidents (
    incident_id VARCHAR(30) NOT NULL,
    link_id VARCHAR(20) NULL,
    occurred_at DATETIME NOT NULL,
    expected_clear_at DATETIME NULL,
    incident_type VARCHAR(20) NOT NULL,
    incident_detail_type VARCHAR(20) NOT NULL,
    road_code VARCHAR(20) NULL,
    tm_x DECIMAL(12, 6) NULL,
    tm_y DECIMAL(12, 6) NULL,
    description TEXT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (incident_id),
    INDEX ix_incident_link_occurred_at (link_id, occurred_at),
    CONSTRAINT fk_incident_link
        FOREIGN KEY (link_id) REFERENCES road_segments (link_id)
        ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 지점별 미래 교통량 예측값
CREATE TABLE IF NOT EXISTS traffic_predictions (
    id BIGINT NOT NULL AUTO_INCREMENT,
    spot_id VARCHAR(20) NOT NULL,
    direction_code TINYINT NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    predicted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    target_at DATETIME NOT NULL,
    predicted_volume INT NOT NULL,
    actual_volume INT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_prediction_spot_direction_target_model
        UNIQUE (spot_id, direction_code, target_at, model_version),
    CONSTRAINT fk_prediction_spot
        FOREIGN KEY (spot_id) REFERENCES traffic_spots (spot_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_prediction_model
        FOREIGN KEY (model_version) REFERENCES model_versions (model_version)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 공영주차장 기준정보
CREATE TABLE IF NOT EXISTS parking_lots (
    parking_code VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    capacity INT NOT NULL DEFAULT 0,
    paid BOOLEAN NOT NULL DEFAULT TRUE,
    restriction VARCHAR(20) NULL,
    operation_type VARCHAR(100) NULL,
    tel VARCHAR(50) NULL,
    coord_source VARCHAR(20) NOT NULL DEFAULT 'SEOUL_API',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (parking_code),
    KEY ix_parking_lots_coords (latitude, longitude),
    KEY ix_parking_lots_restriction (restriction)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 서울시 공영주차장 실시간 현황
CREATE TABLE IF NOT EXISTS parking_realtime (
    parking_code VARCHAR(50) NOT NULL,
    capacity INT NOT NULL DEFAULT 0,
    occupied_spaces INT NOT NULL DEFAULT 0,
    available_spaces INT NOT NULL DEFAULT 0,
    realtime_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    observed_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (parking_code),
    CONSTRAINT fk_parking_realtime_lot
        FOREIGN KEY (parking_code) REFERENCES parking_lots (parking_code)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;


-- 경로 추천 요청 로그 (경로 학습 데이터셋 축적용)
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
    link_match_ratio DOUBLE NULL,
    direction_match_ratio DOUBLE NULL,
    direction_matched_steps INT NULL,
    incident_count INT NULL,
    predicted_volume DOUBLE NULL,
    typical_volume DOUBLE NULL,
    ai_selected BOOLEAN NOT NULL DEFAULT FALSE,
    steps_json JSON NOT NULL,
    coordinates_json JSON NULL,
    link_match_json JSON NULL,
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

-- 서비스링크 → 표준노드링크 구성 순번 (선형 복원 근거)
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

-- 경로 AI 모델 학습 이력 (교통량 model_training_history와 완전 분리)
-- 경로 모델은 RMSE만으로 비교하면 스케일이 달라 교통량 모델과 섞일 수 없다.
-- 채택 기준: top1_accuracy DESC, mean_regret_sec ASC
CREATE TABLE IF NOT EXISTS route_model_training_history (
    id                         BIGINT         NOT NULL AUTO_INCREMENT,
    model_version              VARCHAR(50)    NOT NULL,
    algorithm                  VARCHAR(50)    NOT NULL,
    hyperparameters            JSON           NOT NULL,
    mae                        DECIMAL(12, 4) NOT NULL,
    rmse                       DECIMAL(12, 4) NOT NULL,
    r2_score                   DECIMAL(10, 6) NOT NULL,
    top1_accuracy              DECIMAL(7, 6)  NOT NULL,
    pairwise_ranking_accuracy  DECIMAL(7, 6)  NOT NULL,
    mean_regret_sec            DECIMAL(10, 2) NOT NULL,
    od_top1_accuracy           DECIMAL(7, 6)  NULL,
    od_mean_regret_sec         DECIMAL(10, 2) NULL,
    od_generalizes             BOOLEAN        NULL,
    artifact_path              VARCHAR(500)   NOT NULL,
    trained_at                 DATETIME       NOT NULL,
    accepted                   BOOLEAN        NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    KEY idx_route_training_history_algorithm (algorithm),
    KEY idx_route_training_history_trained_at (trained_at)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 경로 AI 모델 활성 버전 관리
-- is_active=TRUE 인 행 1개가 현재 /api/routes/predict 에서 서빙되는 모델
CREATE TABLE IF NOT EXISTS route_model_versions (
    model_version              VARCHAR(50)    NOT NULL,
    algorithm                  VARCHAR(50)    NOT NULL,
    hyperparameters            JSON           NOT NULL,
    mae                        DECIMAL(12, 4) NOT NULL,
    rmse                       DECIMAL(12, 4) NOT NULL,
    r2_score                   DECIMAL(10, 6) NOT NULL,
    top1_accuracy              DECIMAL(7, 6)  NOT NULL,
    pairwise_ranking_accuracy  DECIMAL(7, 6)  NOT NULL,
    mean_regret_sec            DECIMAL(10, 2) NOT NULL,
    artifact_path              VARCHAR(500)   NOT NULL,
    trained_at                 DATETIME       NOT NULL,
    is_active                  BOOLEAN        NOT NULL DEFAULT FALSE,
    PRIMARY KEY (model_version)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- RoadPulse MySQL schema
-- 실행 대상: AWS RDS의 roadpulse 데이터베이스
-- 여러 번 실행해도 기존 테이블과 데이터는 삭제하지 않습니다.

SET NAMES utf8mb4;

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

-- 머신러닝 모델 버전 및 평가 이력
CREATE TABLE IF NOT EXISTS model_versions (
    model_version VARCHAR(50) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    hyperparameters JSON NOT NULL,
    mae DECIMAL(12, 4) NOT NULL,
    rmse DECIMAL(12, 4) NOT NULL,
    r2_score DECIMAL(10, 6) NOT NULL,
    artifact_path VARCHAR(500) NOT NULL,
    trained_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (model_version)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 모델 학습 시도 전체 이력 및 leaderboard 원본
CREATE TABLE IF NOT EXISTS model_training_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    model_version VARCHAR(50) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    hyperparameters JSON NOT NULL,
    mae DECIMAL(12, 4) NOT NULL,
    rmse DECIMAL(12, 4) NOT NULL,
    r2_score DECIMAL(10, 6) NOT NULL,
    artifact_path VARCHAR(500) NOT NULL,
    trained_at DATETIME NOT NULL,
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    KEY idx_training_history_algorithm_rmse (algorithm, rmse),
    KEY idx_training_history_trained_at (trained_at)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET utf8mb4
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

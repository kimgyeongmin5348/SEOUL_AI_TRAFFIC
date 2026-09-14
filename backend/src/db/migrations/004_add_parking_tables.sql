-- 주차장 기본정보 및 실시간 현황 테이블
SET NAMES utf8mb4;

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
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS parking_realtime (
    parking_code VARCHAR(50) NOT NULL,
    capacity INT NOT NULL DEFAULT 0,
    occupied_spaces INT NOT NULL DEFAULT 0,
    available_spaces INT NOT NULL DEFAULT 0,
    realtime_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    observed_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (parking_code),
    CONSTRAINT fk_parking_realtime_lot FOREIGN KEY (parking_code) REFERENCES parking_lots (parking_code) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

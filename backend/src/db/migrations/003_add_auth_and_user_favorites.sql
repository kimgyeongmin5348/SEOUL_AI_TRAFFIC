SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL AUTO_INCREMENT, email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id), UNIQUE KEY uq_users_email (email)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash CHAR(64) NOT NULL, user_id BIGINT NOT NULL, expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (token_hash),
    KEY ix_user_sessions_user (user_id), KEY ix_user_sessions_expires (expires_at),
    CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS favorite_routes (
    id BIGINT NOT NULL AUTO_INCREMENT, user_id BIGINT NOT NULL,
    origin VARCHAR(255) NOT NULL, destination VARCHAR(255) NOT NULL, label VARCHAR(255) NULL,
    search_count INT NOT NULL DEFAULT 1, avg_time_min INT NULL, current_time_min INT NULL,
    last_searched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (id),
    UNIQUE KEY uq_favorite_route_user_path (user_id, origin, destination),
    KEY ix_favorite_routes_user_rank (user_id, search_count, last_searched_at),
    CONSTRAINT fk_favorite_routes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

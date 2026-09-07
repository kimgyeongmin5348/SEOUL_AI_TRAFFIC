-- 모델 학습 시도 이력 저장 테이블
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

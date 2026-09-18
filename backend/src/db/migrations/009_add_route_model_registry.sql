-- 경로 AI 모델 레지스트리 (교통량 모델과 완전 분리)
-- 경로 예측은 RMSE 단독 비교가 아닌 Top-1 정확도와 Regret 기준으로 모델을 선정합니다.

CREATE TABLE IF NOT EXISTS route_model_training_history (
    id              BIGINT NOT NULL AUTO_INCREMENT,
    model_version   VARCHAR(50) NOT NULL,
    algorithm       VARCHAR(50) NOT NULL,
    hyperparameters JSON        NOT NULL,
    mae             DECIMAL(12, 4) NOT NULL,
    rmse            DECIMAL(12, 4) NOT NULL,
    r2_score        DECIMAL(10, 6) NOT NULL,
    top1_accuracy              DECIMAL(7, 6) NOT NULL,
    pairwise_ranking_accuracy  DECIMAL(7, 6) NOT NULL,
    mean_regret_sec            DECIMAL(10, 2) NOT NULL,
    od_top1_accuracy           DECIMAL(7, 6) NULL,
    od_mean_regret_sec         DECIMAL(10, 2) NULL,
    od_generalizes             BOOLEAN NULL,
    artifact_path   VARCHAR(500) NOT NULL,
    trained_at      DATETIME NOT NULL,
    accepted        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    KEY idx_route_training_history_algorithm (algorithm),
    KEY idx_route_training_history_trained_at (trained_at)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE = utf8mb4_unicode_ci;


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
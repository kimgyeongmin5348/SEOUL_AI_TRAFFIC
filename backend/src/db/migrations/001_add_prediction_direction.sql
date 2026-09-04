-- 기존 RDS에 1회 실행: 학습 기준(spot_id + direction_code)과 예측 결과의 키를 일치시킵니다.
-- 기존 traffic_predictions에 데이터가 있다면 direction_code를 먼저 업무 규칙에 맞게 채운 뒤 실행합니다.

ALTER TABLE traffic_predictions
    ADD COLUMN direction_code TINYINT NOT NULL AFTER spot_id;

ALTER TABLE traffic_predictions
    DROP INDEX uq_prediction_spot_target_model,
    ADD CONSTRAINT uq_prediction_spot_direction_target_model
        UNIQUE (spot_id, direction_code, target_at, model_version);

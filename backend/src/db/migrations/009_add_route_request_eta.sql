-- 경로 모델 ETA 예측값과 적용 여부를 후보 로그에 남깁니다.
-- 이후 actual_duration_sec 라벨과 비교해 온라인 MAE·Top-1·regret를 계산합니다.

ALTER TABLE route_request_candidates
    ADD COLUMN predicted_duration_sec DOUBLE NULL AFTER speed_penalty_sec,
    ADD COLUMN eta_source VARCHAR(20) NULL AFTER predicted_duration_sec;

ALTER TABLE route_requests
    ADD COLUMN route_model_version VARCHAR(50) NULL AFTER model_version,
    ADD COLUMN eta_basis VARCHAR(30) NULL AFTER route_model_version;

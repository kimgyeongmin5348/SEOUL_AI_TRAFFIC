# Work Log

## 2026-09-14

### 경로 추천 1단계

- 학습 데이터 파이프라인에서 기상 데이터의 미래 정보 누수 가능성을 제거했다.
    - `bfill()`과 전체 기간 중앙값 대체를 제거했다.
    - 과거 관측값만 사용하는 `ffill()`을 적용했다.
    - `weather_observed`, `weather_age_hours` 품질 피처를 추가했다.
- 경로 추천 결과에 도로 매칭 품질 정보를 추가했다.
    - 매칭 도로명
    - 미매칭 도로명
    - `match_ratio`
- 매칭 리포트 단위 테스트를 추가했다.
- 수정된 파이프라인으로 `data/processed/traffic_training_dataset.csv`를 재생성했다.
- 시간순 holdout 기준 성능을 측정했다.
    - 기간: `2026-08-27 ~ 2026-08-31`
    - MAE: `188.10`
    - RMSE: `245.38`
    - R²: `0.9005`
- 백엔드 단위 테스트 결과: `30 passed`

### 돌발상황 1차 반영

- `incidents.link_id`와 `road_segments.road_name`을 연결해 활성 돌발을 경로 도로명과 매칭했다.
- 사고·공사·통제·고장 유형별 패널티를 추천 점수에 추가했다.
- 경로별 돌발 건수, 패널티, 상세 목록을 API 응답에 추가했다.
- 경로 상세 화면에 활성 돌발 건수와 반영된 돌발 내용을 표시했다.
- 돌발 패널티 단위 테스트를 추가했다.
- 현재 RDS에서 활성 돌발 10건과 링크-도로명 연결을 확인했다.
- 검증 결과: 백엔드 단위 테스트 `31 passed`, 프론트 빌드 성공

### 돌발상황 공간 매칭 고도화

- OSRM 경로 polyline 좌표를 `/api/routes/predict` 후보 데이터에 추가했다.
- 서울시 GRS80 TM 돌발 좌표를 WGS84로 변환하는 `pyproj` 의존성을 추가했다.
- 도로명 후보 필터 후 경로 polyline 150m 이내 돌발만 추천 점수에 반영하도록 변경했다.
- 동일 도로명이라도 다른 위치의 돌발이 잘못 반영되지 않도록 좌표 기반 테스트를 추가했다.
- 검증 결과: 경로 추천 테스트 `10 passed`, 프론트 빌드 성공

### 돌발 영향 범위·시간 반영

- 실제 AccInfo 코드(`A01`, `A02`, `A04`, `A08`, `A10`)를 사고·고장·공사·통제로 분류했다.
- 유형별 영향 반경을 적용했다: 사고 180m, 고장 120m, 공사 150m, 통제 250m.
- 예상 해제시각이 경로 주행시간과 겹치는 비율을 패널티 가중치에 반영했다.
- 경로 상세 화면에 돌발 분류와 영향 반경을 표시했다.
- 원천 데이터에 진행 방향 필드가 없어 방향 매칭은 아직 보류했다.
- 검증 결과: 경로 추천 테스트 `11 passed`, 프론트 빌드 성공

### 속도·통행시간 데이터셋 확장 및 재학습 비교

- `traffic_speed_measurements`와 primary `traffic_spot_road_maps` 원본 export를 추가했다.
- 속도·통행시간의 1시간 lag와 `speed_data_available`을 학습 데이터셋에 추가했다.
- 대용량 RDS 원본 export는 청크 단위로 변경해 read timeout을 방지했다.
- 확장 데이터셋: `4,882,783행`, `33개 컬럼`
- 속도 피처 유효 행: `4,174행` (`0.0855%`)
- 온라인 경로 추론에도 동일한 속도 lag 피처 생성 경로를 연결했다.
- 확장 XGBoost 재학습 결과: RMSE `178.07`, MAE `94.32`, R² `0.9807`
- 기존 모델보다 성능이 낮아 새 모델은 자동 채택하지 않았다.
- 다음 판단: 속도 수집 커버리지를 높이거나 구간 단위 데이터셋으로 재구성한 뒤 재학습한다.

### 도로 링크 단위 학습 데이터셋 구축

- `link_id`별 속도·통행시간을 시간 단위로 집계했다.
- 1시간 lag와 연속된 다음 시각의 `target_speed_kmh`, `target_travel_time_sec`를 생성했다.
- 과거 기상 관측과 링크별 활성 돌발 유형을 결합했다.
- 기상 관측 이전 행과 다음 시각이 연속되지 않은 행을 제외했다.
- `--link-only` CLI와 `link_feature_meta.json` 메타데이터를 추가했다.
- 생성 결과: `78,036행`, `5,194개 링크`, `28개 컬럼`
- 활성 돌발 포함 행: `489행`, 유형별 합계 `사고 39 / 공사 379 / 통제 60 / 고장 24`
- 기상 피처 결측: `0행`
- 진행 방향 필드는 속도 원천에 없어 다음 단계로 보류했다.

### 링크 속도·통행시간 모델 시간순 평가

- production artifact와 분리된 `scripts/evaluate_link_models.py`를 추가했다.
- 링크 데이터셋의 시간순 holdout 기준일: `2026-09-13 18:00`
- 속도 예측: MAE `2.10km/h`, RMSE `3.27`, R² `0.9469`
- 통행시간 예측: MAE `8.08초`, RMSE `17.17`, R² `0.9190`
- 데이터 기간이 짧고 방향이 분리되지 않아 이번 모델은 운영 artifact로 채택하지 않았다.

### 실시간 속도 추천 점수 반영

- OSRM step에 구간 거리(`distance_m`)를 전달하도록 API 요청을 확장했다.
- 최근 3시간 이내 도로별 최신 속도 관측을 조회하도록 추가했다.
- 관측 속도로 계산한 구간 예상시간이 OSRM 시간보다 큰 경우에만 양의 지연초를 추천 점수에 더했다.
- 경로 상세 화면에 `실시간 속도 반영 지연`을 표시했다.
- 속도 데이터가 없는 구간은 패널티를 0으로 유지하고 미적용으로 표시한다.
- 검증 결과: 경로 추천 테스트 `13 passed`, 프론트 빌드 성공

### 속도 데이터 품질 표시

- 경로별 속도 매칭 도로명과 `speed_match_ratio`를 API 응답에 추가했다.
- 실제 패널티 계산에 사용한 최신 속도 관측 시각을 `speed_observed_at`으로 반환한다.
- 경로 상세 화면에 속도 관측 매칭 범위를 표시해 낮은 커버리지를 숨기지 않도록 했다.
- 검증 결과: 경로 추천 테스트 `13 passed`, 프론트 빌드 성공

### 작업 기준 주석·AI 경로 추천 시각화

- 오늘 추가한 대용량 export, 링크 데이터셋, 돌발·속도 점수, 링크 모델 평가 핵심 로직에 짧은 주석을 보강했다.
- [ai_route_recommendation_flow.html](ai_route_recommendation_flow.html)에 현재 운영 추천과 오프라인 링크 모델 평가 흐름을 standalone HTML로 시각화했다.
- 검증 결과: 백엔드 테스트 `35 passed`, 프론트 빌드 성공

## 2026-09-15

### 링크 방향·기하 정보 조사

- 문제 정의서 기준 진행도를 점검했다: 단계 1 완료, 단계 2 약 80%, 단계 3·4 미착수.
- `road_segments.link_id`는 `1120006300`처럼 10자리 숫자로, 국가교통정보센터 표준노드링크 ID 체계와 형식이 같다. 링크 기하는 표준노드링크 shapefile로 확보할 수 있다.
- `traffic_spot_road_maps`는 이미 `spatial_name_2025`, `spatial_nearest_2025` 방식과 매칭 거리를 저장하고 있다. 즉 지점→링크 공간 매칭은 한 번 수행됐으나 생성 스크립트와 기하 원본이 저장소에 없다.
- 서울시 `LinkWithLoad` API는 `axis_dir`(상행/하행), `link_seq`를 제공한다. `seoul_client.get_road_links`가 이 값을 읽지만 `collector_service.sync_road_segments`가 `road_segments`에 저장하지 않고 버린다.
    - 어제 "원천에 방향 필드 없음"으로 보류한 것은 정정한다. 방향 정보는 원천에 있고 수집 단계에서 누락된 것이다.
- `traffic_volume_measurements`는 `direction_code`, `lane_no`를 보유한다. 추천 단계 `route_prediction.py`가 양방향을 합산하는 것이 문제이며 데이터 부재가 아니다.
- 이 PC에서 RDS 접속이 timeout돼 DB 직접 조회는 못 했다. 위 내용은 `schema.sql`, `data/external/raw_spot_road_maps.csv`, 수집 코드 기준이다.

### 다음 작업

1. `road_segments`에 `axis_code`, `axis_direction`, `link_sequence` 컬럼을 추가하고 `sync_road_segments`가 저장하도록 수정한다.
2. 표준노드링크 기하를 확보해 `road_segments`에 시·종점 좌표 또는 geometry를 추가한다. RDS `link_id`와 표준링크 ID 일치율을 먼저 샘플로 검증한다.
3. OSRM step 좌표를 링크 기하에 map-match하고 진행 방위와 `axis_direction`을 비교해 방향 일치 여부를 저장한다.
4. `route_prediction.py`의 양방향 합산을 제거하고 `direction_code`와 링크 방향의 대응 규칙을 실제 데이터로 확인한다.
5. 매칭 방법·거리·방향 일치율을 API 응답과 링크 데이터셋에 기록한다.
6. 매칭된 링크의 시간대별 `travel_time_sec`로 경로별 `actual_duration_sec`를 재구성하고 품질 등급을 저장한다.
7. `/api/routes/predict` 요청 시 `route_request_id`와 후보 경로를 로그 테이블에 저장해 경로 학습 데이터셋 축적을 시작한다.
8. Top-1 accuracy, pairwise ranking accuracy, regret 계산 스크립트를 추가한다.
9. 화면에 AI 점수가 ETA가 아님을 명시한다.
10. `inbbong` 브랜치를 `main`에 PR로 병합한다.

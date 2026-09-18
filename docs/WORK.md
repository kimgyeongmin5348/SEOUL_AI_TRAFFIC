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

### 도로 링크 축·방향 컬럼 추가 및 수집기 연동

- `road_segments` 테이블에 `axis_code`, `axis_direction`, `link_sequence` 컬럼을 추가했다. (`005_add_road_segments_axis_direction.sql`, `schema.sql`)
- 서울시 `LinkWithLoad` API에서 제공하는 도로 축 코드, 주행 방향(상행/하행), 링크 순번을 `collector_service.sync_road_segments`가 DB에 누락 없이 저장하도록 수정했다.
- 링크 중복 시 최신 축·방향 정보로 업데이트(`ON DUPLICATE KEY UPDATE`)되도록 반영했다.
- 단위 테스트에 축·방향·순번 파라미터 전달 검증을 추가했다.
- 검증 결과: 백엔드 전체 단위 테스트 `35 passed`, 프론트엔드 빌드 성공

### 양방향 교통량 합산 제거 및 주행 방향 매칭

- `route_prediction.py`에서 동일 도로명의 상·하행 관측값을 무조건 합산(`sum`)하던 구조를 제거했다.
- OSRM polyline의 시·종점 좌표를 서울 도심 중심(서울시청)과 비교해 도심 유입(`direction_code=1`) 또는 외곽 유출(`direction_code=2`)을 판별하는 `determine_route_direction` 함수를 추가했다.
- 후보 경로의 주행 방향과 일치하는 방향의 교통량 관측치만 선택해 증가율과 패널티를 계산하도록 수정했다. (반대편 차선의 정체가 내 경로 패널티에 부당하게 가산되는 문제 해소)
- 경로 상세 화면의 예측 교통량 라벨을 `도로별 예측 교통량 (진행 방향)`으로 갱신했다.
- 방향 매칭 및 반대 차선 정체 비간섭 검증 단위 테스트를 추가했다.
- 검증 결과: 백엔드 전체 단위 테스트 `36 passed`, 프론트엔드 빌드 성공

### 화면 AI 추천 점수·비용 성격 명시 (ETA 오해 방지)

- 경로 목록 카드의 시간 옆에 `OSRM 기준` 뱃지를 추가하여 AI가 예측한 도착시간(ETA)으로 오인되지 않도록 했다.
- 경로 주행 상세 분석 상단에 안내 배너를 추가하여, AI 추천 점수가 OSRM 기준시간에 교통량·속도·돌발 패널티를 종합한 "비교 순위용 비용 점수(Cost)"이며 실제 도착시간이 아님을 명시했다.
- 상세 분석 그리드에 `AI 비교 추천 점수` 항목을 추가해 OSRM 기준 소요시간과 종합 비용 점수를 명확히 분리하여 표시했다.
- 프론트엔드 `RouteResult` 타입 및 `routing.ts` 매핑에 `score`, `trafficPenaltySec`, `incidentPenaltySec`를 연결했다.
- 검증 결과: 백엔드 전체 단위 테스트 `36 passed`, 프론트엔드 빌드 성공

### origin/main 병합

- 팀원 챗봇·UI·로고 작업(origin/main 21커밋)을 `inbbong`에 병합했다.
- `frontend/src/pages/Route.tsx` 충돌은 main의 반응형 레이아웃을 유지하고 inbbong의 AI 점수 배너·돌발·속도·진행 방향 항목을 반영해 해결했다.
- 프론트는 pnpm 레이아웃이라 `react-markdown`, `remark-gfm`은 `pnpm@12.4.1`로 설치했다.
- 검증 결과: 백엔드 전체 단위 테스트 `45 passed`, 프론트엔드 빌드 성공
- `origin/inbbong` 푸시 완료, main 대상 PR 생성 대기

### 경로 추천 요청 로그 테이블 (경로 학습 데이터셋 축적 시작)

- `route_requests`(요청 1행)·`route_request_candidates`(후보 1행) 테이블을 추가했다. (`006_add_route_request_logs.sql`, `schema.sql`)
    - 요청: `route_request_id`(uuid4), 요청·출발·목표 시각, 출발지·목적지 이름/좌표, 상태(`ok`/`unavailable`)와 사유, 모델 버전, AI 선택·OSRM 기본 경로 ID, 교통량·기상 관측 시각, 순차 예측 단계 수
    - 후보: OSRM 거리·시간·구간 수, 주행 방향 코드, 점수와 교통량·돌발·속도 패널티, coverage·매칭률, 돌발 건수, 예측·평상 교통량, AI 선택 여부, 원본 `steps_json`·`coordinates_json`, 이후 채울 `actual_duration_sec`·품질 등급 컬럼
- `/api/routes/predict`가 요청마다 `route_request_id`를 발급해 응답에 포함하고, 추천 성공과 보류(`ValueError`) 모두 후보 경로와 함께 저장한다. 로그 저장 실패는 경고만 남기고 추천 응답에 영향을 주지 않는다.
- 요청 스키마에 선택적 `origin`·`destination`(이름·좌표)을 추가했고, 프론트 `routing.ts`가 `PlaceSuggestion`을 전달한다. 없으면 polyline 양 끝 좌표로 대체한다.
- 응답 message의 `도로명 기준 양방향 합산` 문구를 `도로명·진행 방향 기준 교통량 매칭`으로 정정했다.
- RDS에 005(`road_segments` 축·방향 컬럼)와 006 마이그레이션을 적용했다. 실제 세션으로 성공·보류 요청 각 1건을 INSERT해 JSON 컬럼과 FK CASCADE를 확인한 뒤 검증 행은 삭제했다.
- 검증 결과: 백엔드 전체 단위 테스트 `51 passed`, 프론트엔드 빌드 성공

### 서비스링크 선형 복원 (표준노드링크 기하 확보)

- TOPIS `2026-03 서울시 표준링크 매핑정보`(서비스링크→표준링크아이디, 11,572행)와 국가 표준노드링크 `MOCT_LINK` shapefile(156만 링크, EPSG:5186)을 `data/external/`에 확보했다. shp는 600MB라 `.gitignore` 처리했다.
- 서비스링크 ID(`road_segments.link_id`)는 국가 표준링크 ID와 **다른 체계**이며 매핑표로만 연결된다. 어제 "형식이 같다"고 적은 것은 형식만 같은 것이었다.
- `scripts/build_link_geometry.py`를 추가했다. 처리 순서:
    1. 매핑 표준링크 중 500m 이상 떨어진 군집은 매핑 오류로 제외 (DB `road_name` 일치 군집 우선). 155개 서비스링크에서 206개 제외.
    2. `F_NODE→T_NODE` 체인으로 순서 복원. 교차로 내부 링크가 매핑에 없어 끊긴 조각은 끝점 거리로 연결.
    3. 매핑이 구성 표준링크를 일부만 주므로, 매핑 링크 사이 빈 구간을 서울 범위 표준링크 그래프(107,588개) 방향 최단경로로 보충. 2,354개 링크에 7,494개 보충.
    4. 서울시 `LinkWithLoad` 축·방향·순번(`data/external/raw_axis_links.csv`, 532축 5,337링크)으로 이웃 서비스링크 사이 빈 구간을 보충해 양 끝 잘림을 보정. 길이 절반씩 배분하므로 경계는 근사이며 `role=axis_extend`로 구분.
- 결과: 5,341개 중 `complete` 4,667 / `partial` 394(표준링크 일부가 shp에 없음) / `unmapped` 229 / `missing` 51. 도로명 일치 97.3%, 축 이웃 링크 간격 ≤100m 3,966/4,014쌍, DB `length_m` 보유 158개 대비 복원 길이 중앙값 0.965.
- 방향 검증: 같은 축의 상행·하행 평균 방위가 372축 중 99.7%에서 150° 이상 차이 → 선형·순번·방향 정합. 단 **상행/하행은 도심 유입/유출과 무관**(상행 링크의 47%만 시청 방향)하므로 `determine_route_direction`을 `axis_direction`으로 대응시킬 수 없다. 이후 방향 매칭은 링크 `bearing_deg`와 OSRM 구간 방위를 직접 비교한다.
- `007_add_road_segments_geometry.sql`: `road_segments`에 시·종점 좌표, `bearing_deg`, `geometry_length_m`, `geometry_json`, 출처·품질·확장 길이 컬럼 추가, `service_link_standard_links`(구성 표준링크 순번·role) 테이블 추가.
- `pyshp` 의존성 추가. 합성 그래프 단위 테스트 5개 추가.
- 검증 결과: 백엔드 전체 단위 테스트 `56 passed`

### RDS 007 마이그레이션 적용 및 링크 기하 적재

- RDS에 `007_add_road_segments_geometry.sql`을 적용했다. `road_segments`에 시·종점 좌표, `bearing_deg`, `geometry_length_m`, `geometry_json`, 출처·품질·확장 길이 컬럼이 생성되고 `service_link_standard_links` 테이블이 추가됐다.
- `scripts/apply_sql_migration.py`가 프로젝트 루트를 `sys.path`에 넣지 않아 `ModuleNotFoundError: No module named 'backend'`로 실패하던 문제를 수정했다.
- `scripts/build_link_geometry.py --load-db`로 복원 선형을 RDS에 적재했다. 적재 중 두 문제를 수정했다.
    - `service_link_standard_links` PRIMARY(`link_id`, `standard_link_id`) 위반: 빈 구간 최단경로(`gap_fill`)가 이상치로 제외한 표준링크(`outlier`)를 지나면서 같은 표준링크가 두 역할로 중복됐다. `dedupe_sequences`를 추가해 순번 있는 행(실제 선형 구성)을 우선 남기고 순번 없는 `outlier`·`missing` 행이 겹치면 버리며 순번을 1..N으로 재부여한다.
    - 좌표 JSON UPDATE에서 read timeout(30초) 발생: 공유 engine 대신 전용 engine(`read_timeout=600`)과 1,000행 청크로 나눠 적재하도록 `load_to_db`를 수정했다.
- 적재 결과: `service_link_standard_links` 25,514행, `road_segments` 기하 보유 5,061행.
    - 품질: `complete` 4,667 / `partial` 394 / `unmapped` 229 / `missing` 51
    - 역할: `mapped` 10,855 / `gap_fill` 7,493 / `axis_extend` 6,452 / `outlier` 203 / `missing` 511
    - 좌표·방위 보유 5,061건(품질 `unmapped`·`missing` 280건 제외와 일치), 출처 `moct_link_via_topis_mapping_2026_03`
- 중복 제거 단위 테스트 1개를 추가했다.
- 검증 결과: 백엔드 전체 단위 테스트 `57 passed`

### OSRM step → 링크 기하 map-match 및 진행 방위 비교

- `app.py` `RouteStep`에 `coordinates` 필드를 추가해 OSRM step 기하를 받도록 했다.
- 프론트 `routing.ts`가 `step.geometry.coordinates`를 백엔드로 전달한다.
- `route_prediction.py`에 링크 기하 기반 map-match를 구현했다.
    - `bearing_deg`, `bearing_difference`로 진행 방위와 링크 `bearing_deg`를 직접 비교한다. `axis_direction`(상/하행)은 도심 유입/유출과 무관하므로 사용하지 않는다.
    - `load_road_link_geometry`가 007로 적재한 `road_segments` 시·종점 좌표·bearing을 도로명별로 읽는다.
    - `match_step_to_link`가 step 대표점(중간점)에서 60m 이내의 가장 가까운 링크를 찾고, 방위 차이 45도 이내면 방향 일치로 판정한다.
    - 기하가 없거나 60m 밖이면 `link_id=None`, 방향 매칭은 '미적용'으로 남긴다.
- `rank_candidates`가 `link_match_ratio`, `direction_match_ratio`, `direction_matched_steps`, `link_match_details`를 결과에 포함한다.
- `predict_routes`가 링크 기하 인덱스를 로드해 `rank_candidates`에 전달한다.
- 로그 저장: `008_add_route_request_link_match.sql`로 `route_request_candidates`에 `link_match_ratio`, `direction_match_ratio`, `direction_matched_steps`, `link_match_json` 컬럼을 추가하고 `route_request_log.py`가 후보별 매칭 결과를 저장한다.
- 검증: 신규 방위·매칭 단위 테스트 7개 추가, 기존 `predict_routes` mock에 geometry 쿼리 반영.
- 검증 결과: 백엔드 전체 단위 테스트 `64 passed`, 프론트엔드 빌드 성공

### 링크 관측 기반 actual_duration_sec 재구성

- 실제 주행 이력이 없으므로 링크 관측 통행시간으로 경로 통행시간 라벨을 재구성하는 `route_duration_reconstruction.py`를 추가했다.
    - `link_match_details`에 step index를 추가해 `steps_json`과 순서를 맞출 수 있게 했다.
    - `reconstruct_candidate_duration`이 매칭 링크의 `travel_time_sec`로 step 시간을 대체하고, 미매칭 step은 OSRM 시간을 유지한다.
    - `quality_grade`가 링크 매칭률·관측 사용률로 `high`/`medium`/`low` 등급을 남긴다.
    - `RouteDurationReconstructionService`가 출발 시각 ±60분 내 가장 가까운 관측을 링크별로 선택하고, `route_requests` JOIN으로 출발 시각을 참조한다.
- `scripts/reconstruct_route_durations.py` CLI를 추가했다.
- 기존 후보 행은 008 적용 이전에 저장되어 `link_match_json`이 NULL이므로 재구성 대상이 0건이다. 신규 요청부터 actual_duration이 채워진다.
- 검증: 재구성·품질 등급 단위 테스트 4개 추가.
- 검증 결과: 백엔드 전체 단위 테스트 `68 passed`

### 경로 후보 순위 평가 지표 (Top-1, pairwise, regret)

- 문제 정의서 §7의 경로 추천 지표를 계산하는 `route_ranking_evaluation.py`를 추가했다.
    - `top1_accuracy`: 요청별 점수 1위 후보가 실제 통행시간 1위인 비율. 후보 2개 미만 요청은 제외한다.
    - `pairwise_ranking_accuracy`: 요청 내 모든 후보 쌍에서 점수 순서와 실제 순서가 일치하는 비율. 점수·실제가 동점인 쌍은 제외한다.
    - `mean_regret`: 추천 경로와 실제 최적 경로의 통행시간 차이(초) 평균.
    - `RouteRankingEvaluationService`가 `actual_duration_sec`·`score`가 채워진 후보를 요청 단위로 묶고, 품질 등급별 필터도 지원한다.
- `scripts/evaluate_route_ranking.py` CLI를 추가해 overall과 high/medium/low 등급별 지표를 출력한다.
- 검증: 순위 지표 단위 테스트 6개 추가.
- 검증 결과: 백엔드 전체 단위 테스트 `74 passed`

### OD 기반 경로 학습 데이터셋 구축기

- 서울 주요 OD 쌍의 OSRM 후보 경로를 대량 시뮬레이션해 경로 학습 데이터셋을 만드는 `route_training_dataset.py`를 추가했다.
    - `parse_osrm_routes`가 production과 같은 OSRM 응답(alternatives 최대 3, steps)을 후보 목록으로 변환한다.
    - `fetch_osrm_candidates`가 production 프론트와 동일한 공개 OSRM 요청을 사용한다.
    - `build_candidate_record`가 링크 기하 map-match와 관측 통행시간 재구성을 재사용해 후보별 `actual_duration_sec`·`actual_delay_sec`·품질 등급을 계산한다.
    - `assign_ranks`가 동일 요청 내 실제 통행시간 순위와 `chosen_best` 라벨을 부여한다.
    - `RouteTrainingDatasetBuilder`가 OD 쌍·출발 시각별로 후보를 생성하고 출발 시각 ±60분 관측을 링크별로 선택한다.
- `scripts/build_route_training_dataset.py` CLI를 추가했다. 서울 주요 OD 쌍 5쌍과 관측 기간(2026-09-13) 출발 시각 2개를 기본값으로 쓴다. `--limit`, `--sleep`으로 호출량을 제한한다.
- 검증: OSRM 파싱·링크 매칭·재구성·순위·CSV 단위 테스트 7개 추가.
- 검증 결과: 백엔드 전체 단위 테스트 `81 passed`

### 경로 소요시간 회귀 모델 학습 파이프라인

- 경로 학습 데이터셋으로 `actual_duration_sec`를 예측하는 `ml/src/models/route_duration_model.py`를 추가했다.
    - `prepare_dataset`가 출발 시각을 시간순 정렬하고 `departure_hour` 파생 피처와 `direction_match_ratio` 결측 0 채움을 수행한다.
    - `time_split`이 경로 요청이 분할에 섞이지 않도록 시간순으로 train/holdout을 나다.
    - `regression_metrics`가 MAE/RMSE/R²를, `ranking_metrics`가 기존 평가 서비스의 Top-1·pairwise·regret를 재사용해 계산한다.
    - `requests_from_predictions`가 예측 통행시간을 비용 점수(낮을수록 우수)로 변환한다.
- `scripts/train_route_model.py` CLI를 추가했다. 기본은 학습 행이 50개 미만이면 아티팩트를 자동 채택하지 않고, `--force`로 강제 학습할 수 있다.
- 검증: 데이터 준비·시간 분할·회귀 지표·순위 입력·순위 지표·데이터 부족 처리 단위 테스트 6개 추가.
- 파이프라인 스모크 확인: 6행 강제 학습이 end-to-end로 동작(지표는 데이터 부족으로 무의미해 아티트 삭제).
- 검증 결과: 백엔드 전체 단위 테스트 `87 passed`

### 딥시크 작업 검토 및 라벨·map-match 수정

검토 결과 구조(단계 3·4 골격, 순위 지표, 채택 원칙)는 타당했으나 라벨 계산에 실제 데이터로 확인되는 오류가 있어 수정했다.

- **map-match 수정** (`route_prediction.py`)
    - 링크 시·종점 직선 대신 `geometry_json` 폴리라인을 사용한다. 곡선 링크(순환로·램프)는 직선과 실제 도로가 60m 넘게 벌어져 매칭이 빠졌다.
    - step 대표점(중간점) 1개 대신 폴리라인을 100m 간격으로 샘플링해 **링크 여러 개에 길이를 배분**한다(`match_step_to_links`). OSRM step은 1~2km라 링크 2~4개에 걸친다.
    - 거리만으로 최근접 링크를 고르던 것을 **방위 일치(45° 이내) 링크 우선, 그 다음 거리**로 바꿨다. 양방향 도로는 상·하행 링크가 나란히 있어 반대 방향 링크가 더 가까운 경우가 있었다. 반대 방향 링크만 가까운 구간은 `opposite_m`으로 따로 세고 관측에 쓰지 않는다.
    - 링크 방위는 전체 시·종점 방위가 아니라 **샘플점에 가장 가까운 선분의 방위**를 쓴다(곡선 링크 대응).
    - `link_match_ratio`를 고유 도로명 수/step 수에서 **길이 기준**(정의서 `matched_length_ratio`)으로 바꿨다.
- **actual_duration_sec 재구성 수정** (`route_duration_reconstruction.py`)
    - 기존: 매칭 링크의 `travel_time_sec`를 step 시간으로 그대로 대체 → 1,935m step에 746m 링크의 86초가 들어가는 식으로 왜곡. 서울역→강남역 검증에서 OSRM 744초 / 기존 방식 1,235초 / 속도 스케일 1,522초로 값이 제각각이었다.
    - 수정: step에 배분된 링크 길이 × 해당 링크 관측 속도(`speed_kmh`, 없으면 링크 통행시간/링크 길이)로 계산하고, 관측 없는 나머지 길이는 OSRM 시간을 길이 비례로 유지한다.
    - 관측은 주행 중간 시각(출발 + OSRM 시간/2)에 가장 가까운 것을 ±60분 안에서 고른다.
    - 품질 등급을 관측 설명 길이 비율로 정하고(high ≥0.8 / medium ≥0.5 / low ≥0.3), **0.3 미만이면 라벨을 만들지 않고 `unusable`**로 남겨 재처리하지 않는다. 기존에는 관측이 전혀 없어도 OSRM 시간이 라벨이 되고 `chosen_best`가 붙었다.
- **경로 학습 데이터셋 피처 추가** (`route_training_dataset.py`)
    - 출발 시각 이전 관측만 쓰는 `speed_lag_kmh`(길이 가중)·`speed_lag_coverage`, 매칭 링크 위 활성 돌발 `active_incident_count`·유형별 건수, 출발 이전 마지막 기상(108), `departure_hour`·`weekday`·`is_weekend`, `opposite_direction_ratio`, `observed_length_ratio`.
    - OSRM 후보는 OD 쌍당 1회만 조회하고 출발 시각마다 관측만 바꿔 붙인다. OD 쌍을 5→15개로 늘렸다.
    - 출발 시각은 하드코딩 대신 링크 관측이 2,000개 이상인 시간대를 DB에서 자동 선택한다(`observed_departures`). 속도 관측은 9/11~9/15 스케줄러 가동 시간대에만 있다.
    - 라벨 없는 후보는 순위에서 제외하고 라벨 있는 후보가 2개 미만이면 `route_rank_actual`·`chosen_best`를 비운다.
- **모델 학습 파이프라인** (`ml/src/models/route_duration_model.py`)
    - 피처 6개 → 19개. 라벨 없는 행 제외. 속도·기상 결측은 NaN 유지, 비율·건수는 0 채움.
    - 같은 holdout에서 **OSRM 순서 베이스라인**(Top-1·pairwise·regret·MAE)을 함께 계산하고, 정의서 §7대로 Top-1과 regret가 모두 개선되고 MAE가 낮을 때만 채택한다(`beats_baseline`).
    - 아티팩트를 `ml/artifacts/ml_models/`·`reports/`에서 **`ml/artifacts/route_models/`로 분리**했다. 기존 위치는 교통량 모델 `best_saved_model`이 glob하므로 경로 모델 report가 섞이면 "모델 평가 구간이 달라" 오류로 추천이 중단된다.
- 결과
    - 서울역→강남역 A 경로: 링크 매칭 58%→85%, 매칭 링크 7→18개, 반대 방향 0%, 라벨 1,578초(10.7km, 일요일 18시).
    - 데이터셋: 35개 출발 시각 × OD 15쌍 = 525요청 1,015행, 전부 라벨 있음(high 770 / medium 210 / low 35), 관측 설명 길이 중앙값 0.88, 반대 방향 비율 평균 0.03. OSRM 1순위가 실제 1순위와 일치하는 요청 65.3%.
    - 시간순 holdout(165요청): 베이스라인 Top-1 68.2% / regret 178초 / MAE 1,831초 → 모델 **90.3% / 20초 / 319초**. 채택되어 `route_models/route_xgb_duration_v1.joblib` 생성.
    - 한계: OD 15쌍이 train/holdout 양쪽에 있어 **새 OD로의 일반화는 미검증**. 라벨은 링크 관측 속도로 재구성한 값이라 모델이 속도 lag 피처로 유리한 구조다. 온라인 요청 로그의 `actual_duration_sec`는 아직 0건(008 이전 요청만 있음).
- 기타: `.gitignore`에 `route_models/` 추적 규칙 추가, 문제 정의서의 "원천에 방향 없음" 문구 정정, 재구성·매칭·데이터셋·모델 테스트 재작성.
- 검증 결과: 백엔드 전체 단위 테스트 `94 passed`, 프론트엔드 빌드 성공

### origin/main 재병합 및 온라인 라벨 자동화

- 팀원 UI·배포 설정(`render.yaml`, in-process 스케줄러) 커밋을 `inbbong`에 병합했다. 충돌 없음.
- 배포는 Render(web + worker)이고 DB만 AWS RDS다. web 서비스가 무료 플랜이면 15분 유휴 시 잠들어 in-process 스케줄러도 멈춘다. 9/11~9/15 속도 수집 커버리지가 35/120시간(29%)이고 밤마다 16~19시간 끊긴 패턴이 이와 일치한다. worker 서비스 가동 여부를 확인해야 한다.
- 스케줄러에 `route_label_reconstruction` job(1시간 주기)을 추가했다. 출발 후 90분이 지난 요청의 후보에 링크 관측 기반 `actual_duration_sec`를 자동으로 채운다. 서버 시계가 UTC일 수 있어 KST naive로 비교한다.
- `master_sync`(기준정보·축·방향)를 프로세스 시작 직후 한 번 실행하도록 바꿨다. 기존에는 첫 실행이 24시간 뒤라 web 서비스가 잠드는 환경에서는 영영 돌지 않았다.
- 기타 확인: 기상은 ASOS 확정자료 특성상 항상 전일까지만 있으며(설계), `traffic_speed_measurements.measured_at`은 KST, `collected_at`은 UTC로 섞여 있다(정의서 단계 1 "타임존 통일" 미해결).
- 검증 결과: 백엔드 전체 단위 테스트 `96 passed`, 프론트엔드 빌드 성공

## 2026-09-16

### Render worker 24시간 가동 확인

- 9/15 16:12 이후 속도 수집이 20분 이상 끊긴 구간 없음, 9/16 0~17시 전 시간대 수집(링크 5,202개). Render worker가 상시 가동 중이다.
- 온라인 요청 로그: 9/16 00:13 이후 요청에 `link_match_json`이 기록되고 있으며 링크 매칭률 0.75~0.99, 방향 일치 0.88~1.0.
- 팀원 커밋 "시간계산 수정"(#30)이 경로 카드의 소요시간을 OSRM 대신 `score`(비교 비용)로 표시한다. #9와 상충하므로 #13에서 모델 예측 ETA로 교체하기로 조율 필요.

### 경로 학습 데이터셋 완성 (정의서 §5.2·§6 충족)

- **피처 보강** (`route_training_dataset.py`)
    - 속도: `speed_lag_kmh`(길이 가중), `speed_lag_min_kmh`(병목), `speed_lag_travel_time_sec`, `speed_lag_coverage`, `speed_lag_age_min`, `speed_data_available`
    - 교통량: 매칭 링크→측정지점(`traffic_spot_road_maps`)의 출발 전 수집분(`collected_at` UTC 기준) 최신 시간 교통량 `volume_lag_vph_mean`·`volume_lag_vph_max`·`volume_lag_coverage`·`volume_lag_age_hours`. 지점→링크 매핑이 방향을 구분하지 않아 지점 양방향 합계이며 메타데이터에 한계로 명시.
    - 돌발(정의서 5.2 전체): 유형별 건수, `control_length_m`, `blocked_length_m`(전면·차단 표기), `incident_severity_max`(통제 3/사고 2/공사·고장 1), `incident_impact_score`(Σ 심각도×영향 길이 비율×해제 겹침 비율), `incident_clear_overlap_sec`, `incident_match_ratio`, `incident_data_age_sec`. 출발 전에 수집된 활성 돌발만 사용.
    - 기상 `weather_observed_at`, 라벨 관측 시각 `label_observed_at_min/max` 등 누수 검사용 시각 컬럼 추가.
- **누수 자동 검사** `scripts/check_route_dataset.py`: 피처 관측 시각 ≤ 출발 시각, 라벨 관측이 주행 시간대인지, unusable↔라벨 일관성, 요청 단위 순위 1..N·`chosen_best` 1개·1순위=최소 통행시간을 검사하고 위반 시 종료 코드 1.
- **메타데이터** `data/processed/route_feature_meta.json`: 단위·라벨 정의·누수 규칙·알려진 한계·컬럼 역할(identity/feature/timestamp/label/quality)·생성 통계.
- OD 쌍 15→30, 출발 시각은 링크 관측 ≥2,000개인 시간대 자동 선택(최근 14일). `observed_departures` 쿼리가 전체 테이블 GROUP BY로 timeout이 나서 14일로 제한.
- **생성 결과**: 56개 출발 시각(9/11 17시~9/16 18시) × 30쌍 = 1,680요청 **3,136행**, 전부 라벨 있음(high 2,520 / medium 560 / low 56), 순위 있는 요청 1,456. 검사 결과 누수 0행, 위반 0건. 결측: 속도 lag 13%, 교통량 lag 32%.
- **모델 재학습** (`route_duration_model.py`): 피처 35개, `od_split` 추가.
    - 시간순 holdout(510요청): 베이스라인 Top-1 55.7% / regret 271초 / MAE 1,622초 → 모델 **88.0% / 24초 / 176초**
    - **OD holdout(학습에 없는 7쌍, 672행)**: 베이스라인 68.2% / 245초 → 모델 **82.5% / 55초** → 새 OD로 일반화됨(`od_generalizes=True`)
    - 채택되어 `route_models/route_xgb_duration_v1.joblib` 갱신
- 재생성 절차: `build_route_training_dataset.py` → `check_route_dataset.py` → `train_route_model.py`
- 검증 결과: 백엔드 전체 단위 테스트 `98 passed`

## 2026-09-17

### 경로 모델 온라인 추론 연결 및 fallback (#13)

- `route_training_dataset.py`의 DB 로더(활성 돌발·교통량 lag·기상·측정지점 링크)를 모듈 함수로 빼고 `candidate_features`로 묶어, **학습 데이터셋과 온라인 추론이 같은 코드로 피처를 만든다.**
- `route_eta_model.py` 추가
    - `route_models/route_xgb_duration_v1.joblib`을 로드해 후보별 `predicted_duration_sec`를 예측한다. 관측 기준 시각은 요청 시각, 요일·시각 피처는 출발 예정 시각.
    - 자격: 링크 매칭률 ≥ 50%, 속도 관측 커버리지 ≥ 30%. 미달 후보는 `eta_source=osrm`과 사유(`eta_reasons`)를 남긴다.
    - **후보 전부가 자격을 갖출 때만** 예측 ETA 최소 후보를 AI 추천으로 바꾼다(`eta_basis=route_model`). 하나라도 미달이면 기존 휴리스틱 점수 순위를 유지한다(`heuristic_score`).
    - 모델 파일이 없거나 조회·예측 중 예외가 나면 None을 돌려주고 추천은 기존 방식으로 진행된다(경고 로그).
    - 응답 후보마다 `eta_quality`(속도 커버리지·관측 지연 분·평균 속도·교통량 커버리지·활성 돌발·통제 길이·돌발 데이터 지연)를 붙여 근거를 드러낸다.
- `predict_routes`가 휴리스틱 순위 뒤에 모델 ETA를 적용하고, `osrm_comparison.estimated_minutes_saved`를 모델 적용 시 예측 ETA 차이로 계산한다. `message`에 적용/미적용을 명시한다.
- 로그: `009_add_route_request_eta.sql`로 후보에 `predicted_duration_sec`·`eta_source`, 요청에 `route_model_version`·`eta_basis` 추가. RDS 적용 완료. 라벨이 붙으면 `evaluate_route_ranking.py`가 **휴리스틱 / 모델 ETA / OSRM** 세 기준을 같은 요청으로 비교한다.
- 설명(LLM·템플릿): `eta_basis=route_model`이면 "경로 예측 AI는 …"으로 시작해 예측 소요시간·OSRM 기본·속도 반영 비율·관측 지연·돌발 건수를 근거로 쓴다.
- 프론트: 카드 시간 = 모델 ETA(`etaSource=model`)이고 아니면 OSRM. 팀원 #30의 `score`를 시간으로 쓰던 계산을 제거(score는 ETA가 아님). 뱃지 `AI ETA` / `OSRM 기준`, 상세에 AI 예상 시간·OSRM 기본·속도 관측 반영 비율(관측 n분 전)·휴리스틱 점수를 분리 표시. 미적용이면 사유 배너.
- 검증
    - 서울역→강남역 실요청(23시): A ETA 1,482초 / B 1,441초(OSRM 742/784초), 속도 반영 95%/88%, 관측 4분 전. 휴리스틱은 A, 모델은 B 선택.
    - API end-to-end(TestClient + RDS): 응답·로그(`predicted_duration_sec`, `eta_source`, `route_model_version`)·설명문 확인 후 검증 행 삭제.
    - 단위 테스트 8개 추가(자격·zero-fill·공유 피처·미자격·모델 없음/예외 fallback·순위 교체·부분 미달 시 휴리스틱 유지). 백엔드 전체 `106 passed`, 프론트 빌드 성공.

## 2026-09-18

### 배포 확인 및 추천 사유 문장 분리 버그 수정

- #13 배포 확인: 온라인 요청 로그에 `eta_basis=route_model` 요청이 기록되기 시작했다(총 57요청 중 배포 후 4건). 라벨(`actual_duration_sec`)은 아직 0건 — 라벨 job은 출발 90분 후 실행되므로 요청이 더 쌓여야 한다.
- 화면 "이 경로를 고른 이유"가 "예상 소요시간은 약 20." / "6분(OSRM 기본 3." 으로 끊기는 버그를 고쳤다.
    - 원인: `Route.tsx`의 문장 분리 정규식 `[^.!?]+[.!?]?`가 소수점을 문장 끝으로 취급. LLM·템플릿 문장 모두 영향.
    - 수정: "마침표·물음표·느낌표 뒤 공백"에서만 분리(`split(/(?<=[.!?])\s+/)`).
    - 템플릿(`route_explainer.py`): 분·퍼센트를 정수로, "다음 후보 B(약 22분)보다 2분 빠릅니다" 형태로 정리. LLM 프롬프트에 "수치는 정수로" 지시 추가.
- 스크린샷의 3km 경로(대학로·율곡로) AI 예상 21분 vs OSRM 3분은 7배로, 학습 데이터에 짧은 도심 경로가 적어(OD 30쌍 모두 5~15km) 과대 예측 가능성이 있다. 온라인 라벨이 붙으면 실제값과 비교한다.
- 검증 결과: 설명 테스트 `4 passed`, 프론트엔드 빌드 성공

## 2026-09-19

### 배포 환경 AI 경로 추천 503 및 메인화면 캐시 문제 수정

- 증상: 배포 사이트에서 `/api/routes/predict`가 503을 반환해 AI 추천 대신 fallback으로 동작하고(F5로도 복구 안 됨), 메인화면은 첫 진입 시 예전 빌드가 보이다가 F5를 누르면 최신으로 바뀜. 로컬은 정상.
- 원인 1 (AI 503): `4abe7ef chore: remove deployment-unnecessary files`에서 `ml/src/`가 통째로 삭제됐는데 `route_prediction.py`의 `predict_routes`·`predict_spot_series`가 여전히 `from ml.src.util.config import ROUTE_FEATURE_COLUMNS, ROUTE_ZERO_FILL_COLUMNS`를 호출 → 배포 서버에서 `ModuleNotFoundError: No module named 'ml.src'`. Dockerfile도 `backend/`와 `ml/artifacts/`만 복사하므로 `ml/src`는 원래 이미지에 들어가지 않는다. 로컬은 삭제 커밋을 받기 전이거나 `ml/src` 복사본이 남아 있어 통과했다.
    - 수정: `backend/src/services/route_features.py`를 추가해 추론에 필요한 두 상수(피처 35개, zero-fill 16개)를 backend 안으로 옮기고 두 import를 `backend.src.services.route_features`로 변경.
    - 검증: 서빙 중인 `route_lightgbm_duration_v1_tuned.joblib`·`route_xgboost_duration_v1_tuned.joblib`의 `feature_columns`와 옮긴 목록이 순서까지 일치. 모델 파일 내부에 `ml.src` 참조 없음. `backend.src.api.app` import 성공.
- 원인 2 (메인화면 예전 빌드): `app.py`의 SPA fallback이 `index.html`을 캐시 헤더 없이 내려보내 브라우저가 이전 `index.html`(옛 해시 번들을 가리킴)을 재사용.
    - 수정: `index.html` 응답에 `Cache-Control: no-cache` 추가. 해시가 붙는 `/assets/*`는 그대로 캐시.
- 남은 문제: `backend/tests/unit/test_route_duration_model.py`, `scripts/evaluate_link_models.py`는 아직 `ml.src`를 import해 현재 저장소에서 실행 불가. 배포에는 영향 없음. 학습 파이프라인을 계속 쓰려면 `ml/src` 삭제를 되돌리거나 해당 스크립트를 정리해야 한다(팀 결정 필요).

### 다음 작업

1. [완료] `road_segments`에 `axis_code`, `axis_direction`, `link_sequence` 컬럼을 추가하고 `sync_road_segments`가 저장하도록 수정한다.
2. [완료] 표준노드링크 기하를 확보해 `road_segments`에 시·종점 좌표 또는 geometry를 추가한다. (TOPIS 매핑표로 연결, 007 RDS 반영 완료)
3. [완료] OSRM step 좌표를 링크 기하에 map-match하고 진행 방위와 링크 `bearing_deg`를 비교해 방향 일치 여부를 저장한다. (008 RDS 적용 완료)
4. [완료] `route_prediction.py`의 양방향 합산을 제거하고 `direction_code`와 링크 방향의 대응 규칙을 실제 데이터로 확인한다.
5. [완료] 매칭 방법·거리·방향 일치율을 API 응답(`link_match_ratio`, `direction_match_ratio`)과 로그(`link_match_json`)에 기록한다.
6. [완료] 매칭된 링크의 시간대별 `travel_time_sec`로 경로별 `actual_duration_sec`를 재구성하고 품질 등급을 저장한다.
7. [완료] `/api/routes/predict` 요청 시 `route_request_id`와 후보 경로를 로그 테이블에 저장해 경로 학습 데이터셋 축적을 시작한다.
8. [완료] Top-1 accuracy, pairwise ranking accuracy, regret 계산 스크립트를 추가한다.
9. [완료] 화면에 AI 점수가 ETA가 아님을 명시한다.
10. [완료] `inbbong` 브랜치를 `main`에 PR로 병합한다. (반복 병합 중; 라벨 job 커밋은 PR 대기)
11. [완료] 서울시 주요 출발·도착지(OD) 쌍 기반으로 과거 OSRM 후보 경로를 대량 시뮬레이션 생성하고 링크 관측과 결합해 `route_training_dataset.csv`를 일괄 구축한다. (Cold Start 해소)
12. [완료] 경로 실제 소요시간(`actual_duration_sec`) 회귀 모델을 학습하고 아티팩트(`ml/artifacts/route_models`)를 생성한다.
13. [완료] `route_prediction.py`에 경로 모델 ETA 추론을 연결하고 자격 미달·오류 시 휴리스틱으로 fallback한다. (009 RDS 적용, PR·배포 대기)
14. [완료] OD 단위 holdout(학습에 없는 OD 쌍으로 검증)을 추가해 새 경로 일반화 성능을 측정한다. (30쌍, holdout 7쌍 Top-1 82.5%)
15. 배포 후 온라인 라벨이 쌓이면 `evaluate_route_ranking.py`로 휴리스틱 / 모델 ETA / OSRM의 Top-1·regret를 같은 요청으로 비교한다.
16. [배포 후 자동] `road_segments.axis_*` 컬럼을 채운다 — `master_sync`가 시작 직후 실행되도록 변경.
17. [완료] Render worker 24시간 가동 확인.
18. `measured_at`(KST)·`collected_at`(UTC) 타임존 혼재를 정리한다.
19. 9/19 데이터셋 재생성(`build → check → train`)으로 9일치 관측 기준 최종 모델을 만들고 문서 수치를 갱신한다.
20. 짧은 도심 경로(3km 이하)의 모델 ETA 과대 예측 여부를 온라인 라벨로 확인하고, 필요하면 OD에 단거리 쌍을 추가해 재학습한다.

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

### 다음 작업

1. [완료] `road_segments`에 `axis_code`, `axis_direction`, `link_sequence` 컬럼을 추가하고 `sync_road_segments`가 저장하도록 수정한다.
2. [완료] 표준노드링크 기하를 확보해 `road_segments`에 시·종점 좌표 또는 geometry를 추가한다. (TOPIS 매핑표로 연결, RDS에 007 적용 후 `--load-db`로 5,061건 적재 완료)
3. OSRM step 좌표를 링크 기하에 map-match하고 진행 방위와 링크 `bearing_deg`를 비교해 방향 일치 여부를 저장한다. (`axis_direction`은 유입/유출과 무관하므로 방위 직접 비교)
4. [완료] `route_prediction.py`의 양방향 합산을 제거하고 `direction_code`와 링크 방향의 대응 규칙을 실제 데이터로 확인한다.
5. 매칭 방법·거리·방향 일치율을 API 응답과 링크 데이터셋에 기록한다.
6. 매칭된 링크의 시간대별 `travel_time_sec`로 경로별 `actual_duration_sec`를 재구성하고 품질 등급을 저장한다.
7. [완료] `/api/routes/predict` 요청 시 `route_request_id`와 후보 경로를 로그 테이블에 저장해 경로 학습 데이터셋 축적을 시작한다.
8. Top-1 accuracy, pairwise ranking accuracy, regret 계산 스크립트를 추가한다.
9. [완료] 화면에 AI 점수가 ETA가 아님을 명시한다.
10. [진행 중] `inbbong` 브랜치를 `main`에 PR로 병합한다. (origin/main 병합·푸시 완료, PR 생성 대기)
11. 서울시 주요 출발·도착지(OD) 쌍 기반으로 과거 OSRM 후보 경로를 대량 시뮬레이션 생성하고 링크 관측과 결합해 `route_training_dataset.csv`를 일괄 구축한다. (Cold Start 해소)
12. 경로 실제 소요시간(`actual_duration_sec`) 회귀 또는 후보 간 순위 학습(Pairwise Ranking) AI 모델을 학습하고 아티팩트(`ml/artifacts/ml_models`)를 생성한다.
13. `route_prediction.py`의 휴리스틱 추천 방식을 신규 경로 AI 모델 추론으로 교체하고, 매칭 데이터 부족 시 기존 방식으로 안전하게 fallback하도록 연동한다.

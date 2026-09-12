# 🚦 RoadPulse - 서울시 AI 실시간 교통량 예측 시스템

RoadPulse는 서울시 주요 139개 도로 검지기 지점의 2년 치 교통량 빅데이터와 기상청 기상 관측 데이터를 결합하여 미래 교통량을 예측하는 머신러닝 기반 지능형 교통 시스템입니다

---

## 🗂️ 프로젝트 전체 구조

```text
SEOUL_AI_TRAFFIC/
├── backend/                         # 백엔드 및 데이터 처리 로직
│   └── src/
│       ├── core/
│       │   └── config.py             # 환경변수 및 애플리케이션 설정
│       ├── api/
│       │   └── routes/               # FastAPI 엔드포인트별 라우터
│       ├── db/
│       │   ├── database.py           # SQLAlchemy DB 연결 및 세션
│       │   └── schema.sql            # MySQL 테이블 및 외래키 스키마
│       ├── repositories/             # DB 조회·저장 로직
│       ├── schemas/                  # API 요청·응답 Pydantic 스키마
│       ├── utils/                    # 공통 유틸리티
│       ├── workers/                  # 스케줄러·백그라운드 작업
│       └── services/
│           ├── seoul_client.py       # 서울시 TOPIS OpenAPI 호출
│           ├── kma_client.py         # 기상청 ASOS API 호출
│           ├── collector_service.py  # API 데이터 수집 및 DB 적재
│           └── data_pipeline.py      # DB 추출, 병합, Feature Engineering
│   └── tests/
│       ├── unit/                     # 단위 테스트
│       └── integration/              # DB·API 통합 테스트
│
├── frontend/                        # React + TypeScript 사용자 화면
│   ├── src/
│   │   ├── components/               # 공통 UI: 사이드바, 네비게이션, 지도
│   │   ├── hooks/                    # 재사용 React hooks
│   │   ├── layouts/                  # 화면 공통 레이아웃
│   │   ├── pages/                    # 대시보드, 교통, 날씨, 예측 등 화면
│   │   ├── services/                 # 백엔드 API 호출 모듈
│   │   ├── components/DataPage.tsx    # DB 수집본 조회 화면
│   │   ├── types/                    # 프론트엔드 TypeScript 타입
│   │   ├── utils/                    # 프론트엔드 공통 유틸리티
│   │   ├── App.tsx                   # 페이지 라우팅
│   │   ├── main.tsx                  # 프론트엔드 진입점
│   │   └── index.css                 # 전역 스타일
│   ├── package.json                  # 프론트엔드 의존성 및 실행 명령
│   └── vite.config.ts                # Vite 설정
│
├── scripts/                         # 팀원이 직접 실행하는 작업용 CLI
│   ├── collect_data.py               # 최신 교통·기상·돌발 데이터 수집
│   ├── process_data.py               # DB 데이터를 학습용 CSV로 전처리
│   └── import_traffic_excel.py       # 교통량 엑셀 원본 일괄 적재
│
├── data/                             # 대용량 데이터 저장소 (Git 제외)
│   ├── raw/                          # DB에서 추출한 원본 데이터
│   ├── external/                     # 지점 좌표 등 외부 보조 데이터
│   └── processed/                    # 모델 학습용 최종 데이터셋
│
├── docs/
│   ├── api/                          # API 명세
│   ├── architecture/                # ERD 및 시스템 설계 문서
│   └── database/                     # 테이블·인덱스·적재 규칙 문서
├── infra/
│   ├── aws/                          # AWS 리소스 및 운영 설정
│   ├── docker/                       # 컨테이너 설정
│   └── terraform/                    # Infrastructure as Code
├── ml/
│   ├── models/                       # LightGBM·XGBoost 모델별 영역
│   ├── artifacts/                    # 학습된 .joblib 및 학습 결과 메타데이터
│   ├── notebooks/                    # 탐색·실험용 노트북
│   └── src/
│       ├── models/                   # 모델별 학습·추론 코드
│       │   ├── lightgbm/
│       │   └── xgboost/
│       └── util/                     # 공통 경로·분할·평가·DB 등록
├── main.py                           # FastAPI 서버 실행 진입점
├── pyproject.toml                    # Python 의존성 및 개발 도구 설정
├── uv.lock                           # Python 의존성 잠금 파일
├── .gitignore                        # 환경변수 및 대용량 파일 제외 설정
└── README.md                         # 프로젝트 문서 및 팀원 작업 가이드
```

### 폴더별 담당 작업

| 위치 | 여기서 해야 할 작업 |
| :--- | :--- |
| `backend/src/db/` | DB 테이블을 추가·수정하거나 연결 설정을 관리합니다. 스키마 변경 시 ERD도 함께 갱신합니다. |
| `backend/src/services/` | 외부 API 연동, 데이터 수집, DB 적재, 전처리 로직을 구현합니다. API 키는 코드에 직접 작성하지 않습니다. |
| `frontend/src/components/` | 여러 화면에서 재사용하는 UI 컴포넌트를 작성합니다. |
| `frontend/src/pages/` | 사용자 기능별 화면을 구현합니다. 실제 DB 조회 API를 사용하며, 결측과 오류를 구분해 표시합니다. |
| `frontend/src/data/` | 가상 측정값은 사용하지 않습니다. |
| `scripts/` | 데이터 수집·적재·전처리처럼 반복 실행할 작업을 CLI 스크립트로 추가합니다. |
| `data/` | 원본·중간·학습 데이터를 저장합니다. 대용량 파일은 Git에 커밋하지 않습니다. |
| `ml/src/models/` | LightGBM·XGBoost별 학습·추론 코드를 구현합니다. |
| `ml/src/util/` | 모델 공통 학습, 시간순 분할, 평가, 경로, Artifact 저장, DB 등록을 관리합니다. |
| `ml/artifacts/` | 학습된 `.joblib`와 학습 결과 메타데이터를 저장합니다. |
| `docs/` | ERD, API 명세, 실행 방법 등 팀 협업에 필요한 설계 문서를 관리합니다. |

### 작업 시 기본 원칙

> Git은 파일을 추적하는 시스템이라 빈 폴더 자체는 커밋하지 않습니다. 따라서 현재 작업 대상이 없는 폴더에도 `.gitkeep` 또는 `README.md`를 두어 팀원이 clone/pull 후 동일한 구조를 받도록 합니다.

1. 기능별로 담당 폴더에 코드를 작성하고, 임시 파일이나 대용량 데이터는 커밋하지 않습니다.
2. 환경변수와 API 키는 `backend/.env`에만 저장하며 README나 소스 코드에 노출하지 않습니다.
3. DB 스키마를 변경하면 `backend/src/db/schema.sql`과 `docs/architecture/`의 ERD를 함께 수정합니다.
4. 프론트 화면을 수정한 뒤 `frontend` 폴더에서 `pnpm build`로 타입 및 빌드를 확인합니다.
5. 데이터 처리 로직을 수정한 뒤 샘플 데이터로 결과 컬럼, 결측치, 행 수를 확인합니다.

---

## 👥 팀원을 위한 빠른 시작 가이드 (Quick Start)

### 1. 개발 환경 세팅
본 프로젝트는 초고속 패키지 관리자 **`uv`** (또는 pip)를 사용합니다.

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/SEOUL_AI_TRAFFIC.git
cd SEOUL_AI_TRAFFIC

# 2. 가상환경 생성 및 의존성 패키지 일괄 설치
uv sync
```

### 2. 환경변수(`.env`) 설정
AWS RDS MySQL 데이터베이스 접속 정보를 `backend/.env` 파일로 생성합니다. (팀 공유 정보 활용)

### 3. RDS 테이블 이해하기

테이블은 크게 **기준정보**, **실측 시계열**, **AI 모델/예측**, **사용자 기능** 네 영역으로 나뉩니다. 이름에 `measurements`가 붙은 테이블은 시간이 지날수록 계속 누적되는 실측 데이터이고, 기준정보 테이블은 측정지점이나 도로의 이름과 식별자를 보관합니다.

#### 기준정보 테이블

| 테이블 | 무엇을 저장하나 | 주요 키·컬럼 | 어디에 사용하나 |
|---|---|---|---|
| `traffic_spots` | 서울시 `SpotInfo` 교통량 측정지점 | `spot_id`(PK), `spot_name`, `tm_x`, `tm_y`, `latitude`, `longitude` | 교통량 데이터의 지점 이름·위치 확인, AI 학습 및 도로 검색 |
| `road_segments` | 서울시 `LinkInfo` 도로 링크 | `link_id`(PK), `road_name`, 시작·종료 노드, `length_m`, `region_code` | 링크별 실시간 속도와 돌발상황을 실제 도로명에 연결 |
| `weather_stations` | 기상청 ASOS 관측소 | `weather_station_id`(PK), `station_name`, 위·경도, 고도, 활성 여부 | 날씨 측정값의 관측소 정보 제공 |
| `traffic_spot_road_maps` | 교통량 지점과 도로 링크의 연결표 | `(spot_id, link_id)`(복합 PK), 매칭 거리·방식, 대표 링크 여부 | 지점 단위 교통량을 경로의 도로 링크와 결합하는 다대다 매핑 |

#### 실측 시계열 테이블

| 테이블 | 한 행의 의미 | 주요 키·컬럼 | 주의할 점 |
|---|---|---|---|
| `traffic_volume_measurements` | 특정 지점·시각·방향·차로의 교통량 | `spot_id`, `measured_at`, `direction_code`, `lane_no`, `traffic_volume` | AI 교통량 모델의 핵심 학습 데이터. 지점·시각·방향·차로 조합은 중복 저장되지 않음 |
| `traffic_speed_measurements` | 특정 도로 링크의 시각별 평균속도와 통행시간 | `link_id`, `measured_at`, `speed_kmh`, `travel_time_sec` | 지도 혼잡도와 실시간 도로 상태에 사용. 링크·측정시각 조합은 유일함 |
| `weather_measurements` | 특정 관측소의 시간별 날씨 | `weather_station_id`, `observed_at`, 기온·강수·습도·풍속·풍향·기압 | 교통량 예측의 외생 변수. 무강수 시간의 `rainfall_mm=NULL`은 모델 입력 시 0으로 처리 |
| `incidents` | 사고·공사·고장·통제 등 돌발상황 한 건 | `incident_id`(PK), `link_id`, 발생·해제예정 시각, 유형, `tm_x`, `tm_y`, 설명 | 지도 마커와 경로 참고 정보. 좌표는 GRS80TM(WTM)이며 화면에서 WGS84로 변환 |

#### AI 모델 및 예측 테이블

| 테이블 | 무엇을 저장하나 | 주요 키·컬럼 | 사용 목적 |
|---|---|---|---|
| `model_versions` | 실제 배포 가능한 모델 버전과 성능 | `model_version`(PK), 알고리즘, 하이퍼파라미터, MAE·RMSE·R², 모델 파일 경로, 활성 여부 | 어떤 학습 모델을 운영에 사용할지 관리 |
| `model_training_history` | 채택 여부와 관계없는 모든 학습 시도 | 모델 버전, 알고리즘, 성능지표, 학습시각, `accepted` | 실험 비교와 leaderboard 이력 보존. 배포 모델 테이블과 역할이 다름 |
| `traffic_predictions` | 모델이 생성한 지점·방향별 미래 교통량 | `spot_id`, `direction_code`, `model_version`, 생성시각, 목표시각, 예측값, 실제값 | AI 예측 화면과 온라인 성능 평가. 목표시각이 지난 뒤 `actual_volume`을 채워 오차 계산 |

#### 사용자 기능 테이블

| 테이블 | 무엇을 저장하나 | 주요 키·컬럼 | 보안·관계 |
|---|---|---|---|
| `users` | 로그인 사용자 계정 | `id`(PK), 고유 이메일, `password_hash`, 가입시각 | 비밀번호 원문은 저장하지 않고 PBKDF2-SHA256 해시만 저장 |
| `user_sessions` | 로그인 세션 | `token_hash`(PK), `user_id`, 만료시각 | 쿠키 원문 대신 토큰 해시를 저장하며 사용자 삭제 시 함께 삭제 |
| `favorite_routes` | 사용자별 경로 검색 및 즐겨찾기 집계 | `user_id`, 출발지, 도착지, 라벨, 검색 횟수, 최근 검색시각 | 같은 사용자의 동일 출발지·도착지는 한 행으로 누적되고 다른 사용자 데이터와 분리 |

핵심 관계는 다음과 같습니다.

- `traffic_spots` → `traffic_volume_measurements`, `traffic_predictions`: 한 측정지점에 여러 시간대 실측·예측값이 연결됩니다.
- `road_segments` → `traffic_speed_measurements`, `incidents`: 한 도로 링크에 여러 시간대 속도와 돌발상황이 연결됩니다.
- `weather_stations` → `weather_measurements`: 한 관측소에 시간별 날씨가 누적됩니다.
- `traffic_spots` ↔ `road_segments`: `traffic_spot_road_maps`를 통해 지점과 링크를 연결합니다.
- `model_versions` → `traffic_predictions`: 각 예측값이 어떤 모델에서 생성됐는지 추적합니다.
- `users` → `user_sessions`, `favorite_routes`: 계정별 세션과 경로 이력을 분리합니다.

`measured_at`, `observed_at`, `occurred_at`, `target_at`은 데이터가 실제로 관측·발생·예측되는 업무 시각이고, `collected_at` 또는 `predicted_at`은 시스템이 DB에 수집하거나 예측을 생성한 시각입니다. 두 종류의 시각을 혼동하지 마세요. 전체 컬럼과 제약조건은 [`backend/src/db/schema.sql`](backend/src/db/schema.sql), 인증 테이블 설명은 [`docs/database/README.md`](docs/database/README.md)를 참고하세요.


---

## 📊 ★ AI 모델 학습용 데이터셋 준비 방법 (팀원 필독!)

> **⚠️ 대용량 데이터 Git 미포함 안내**  
> 전처리된 학습 데이터(`traffic_training_dataset.csv`)는 **약 487만 행(1GB 이상)**으로 GitHub 파일 용량 제한(100MB)을 초과하므로 Git에 커밋되지 않습니다. 대신 이미 **클라우드 DB(AWS RDS)에 2년 치 전수 데이터가 완벽히 구축**되어 있습니다.

팀원은 프로젝트를 클론한 후, **터미널에서 아래 명령어 딱 한 줄만 실행**하면 본인 컴퓨터에 자동으로 487만 행짜리 정제 데이터셋이 1분 만에 생성됩니다!

```bash
# RDS DB에서 488만 건을 가져와 결측치 0인 전처리 학습 데이터셋 자동 생성
uv run python scripts/process_data.py
```

### 📁 생성되는 산출물 확인
* `data/processed/traffic_training_dataset.csv`: **4,871,862 행 $\times$ 27 컬럼** (결측치 0건 완전 데이터셋)
* `data/processed/feature_meta.json`: 27개 특성 컬럼 메타데이터 정의서

---

## 🛠️ 프로젝트 주요 스크립트 안내

| 실행 명령어 | 설명 |
| :--- | :--- |
| `uv run python scripts/process_data.py` | **[팀원 권장]** DB $\rightarrow$ 전처리 $\rightarrow$ `data/processed/` 학습 데이터셋 자동 생성 |
| `uv run python scripts/collect_data.py --status` | RDS 데이터베이스 현재 적재 현황 및 레코드 수 확인 |
| `uv run python scripts/collect_data.py --all` | 서울시 전체 도로 링크 기준정보와 최신 교통·기상·돌발 데이터 일괄 수집 |
| `uv run python scripts/run_realtime_scheduler.py` | 전체 등록 링크의 속도·돌발(5분), 교통량·날씨(1시간) 자동 수집 |
| `uv run python scripts/export_realtime_test.py` | 완료된 예측에 실제 교통량을 연결하고 온라인 Test CSV 생성 |
| `uv run python scripts/import_traffic_excel.py --all-spots` | `data/raw/` 내 24개 엑셀 파일 전수 DB 벌크 적재 |


---

## 📈 데이터셋 주요 특성 (27개 컬럼)

* **정답 라벨 ($y$)**: `target_volume` (지점/방향/시간별 실제 통행 교통량)
* **기상 실측치**: `temperature_c`(기온), `rainfall_mm`(강수량), `humidity_pct`(습도), `wind_speed_ms`(풍속), `pressure_hpa`(기압)
* **시계열 지연(Lag)**: `vol_lag_1h`(1시간 전), `vol_lag_2h`(2시간 전), `vol_lag_24h`(어제 동시간대 교통량)
* **이동 통계(Rolling)**: `vol_rolling_mean_3h`(최근 3시간 평균), `vol_rolling_mean_24h`(최근 24시간 평균)
* **시간 및 주기성**: `hour`, `dayofweek`, `is_weekend`, `month`, `is_rush_hour`(출퇴근 피크 플래그), 삼각함수 순환 인코딩(`hour_sin`, `hour_cos`, `day_sin`, `day_cos`)

## 실시간 운영 데이터 흐름

`traffic_training_dataset.csv`는 시간순 8:2 분할 후 모델 학습과 오프라인 검증에 사용하며, 실시간 API 데이터로 덮어쓰지 않습니다. 실시간 수집 데이터는 RDS 측정 테이블에 누적하고, 모델이 생성한 예측은 `traffic_predictions`에 저장합니다. 예측 대상 시간이 지난 후 실제 교통량을 `actual_volume`에 연결하고 `data/online/realtime_test_dataset.csv`로 내보내 온라인 성능을 평가합니다.
## DB 연결 화면 실행

```powershell
uv run python main.py
# 별도 터미널
cd frontend
pnpm dev
```

화면: http://localhost:5173/dashboard. Vite의 `/api` 프록시가 로컬 8000번 FastAPI 서버로 연결합니다.
배포 시에도 `/api`를 백엔드로 전달하는 reverse proxy가 필요합니다.
`GET /api/data/{traffic|speed|weather|incidents|prediction}`은 기존 DB에서 최대 500행을 조회합니다.
교통량은 최신 측정 시각의 지점/방향별 차로 합계, 속도는 최신 시각의 수집 링크,
날씨는 최신 관측일의 시간별 값, 돌발은 마지막 수집일의 이력, 예측은 최신 생성 묶음입니다.
측정 시각은 한국시간으로 표시하며, 자동 수집이나 실시간 갱신은 화면 실행만으로 시작되지 않습니다.
빈 DB와 연결 실패를 별도로 표시하며, 예측·경로·날씨 예보를 가상값으로 채우지 않습니다.

오늘 재수집: `uv run python scripts/collect_data.py --all`.
ASOS 날씨 기본 조회는 한국시간 어제 00~23시입니다. 전일 자료 공개가 지연되면 다시 수집해야 합니다.
기상청 안내: https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36

## Render 배포

루트의 `render.yaml`을 Blueprint로 가져오면 React 정적 빌드와 FastAPI가 하나의 Docker 웹 서비스로 배포됩니다. 동일 출처에서 `/api`와 화면을 제공하므로 로그인 쿠키를 위한 별도 CORS 설정은 필요하지 않습니다.

1. 변경사항과 `ml/artifacts/ml_models`, `ml/artifacts/reports`의 배포용 모델 파일을 GitHub에 푸시합니다.
2. Render Dashboard에서 **New > Blueprint**를 선택하고 이 저장소를 연결합니다.
3. Blueprint 생성 화면에서 `DATABASE_URL`과 필요한 서울시·기상청 API 키를 Secret으로 입력합니다.
4. 배포 완료 후 `/api/health`가 `{"status":"ok"}`를 반환하는지 확인합니다.

`DATABASE_URL` 예시 형식은 `mysql+pymysql://USER:PASSWORD@HOST:3306/roadpulse`입니다. 실제 비밀번호와 API 키는 Git에 커밋하지 않습니다. AWS RDS 보안 그룹도 Render 서비스의 아웃바운드 연결을 허용해야 합니다.

Render의 Auto-Deploy가 켜져 있으므로 이후 `main` 브랜치에 푸시하면 자동 재배포됩니다. DB 마이그레이션은 앱 시작 시 자동 실행하지 않으며, 배포 전에 검토 후 `python -m scripts.apply_sql_migration <파일명>`으로 별도 적용합니다.

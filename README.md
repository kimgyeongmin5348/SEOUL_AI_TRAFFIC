# 🚦 RoadPulse (Seoul AI Traffic)
> **AI 기반 서울시 교통량 예측 및 최적 경로 추천 서비스**

[![RoadPulse Main](./docs/main_screen.jpg)](https://roadpulse-a2sz.onrender.com)
*(이미지를 클릭하면 웹사이트로 이동합니다)*

## 📖 1. 프로젝트 소개
**RoadPulse**는 서울시의 주요 도로 교통량을 AI 모델을 통해 예측하고, 단순한 최단 거리가 아닌 **'실제 교통 상황을 반영한 최적의 경로'**를 추천해주는 웹 서비스입니다. 
경로가 추천된 이유를 LLM(거대 언어 모델) 기반의 챗봇 기능을 통해 자연스러운 문장으로 설명하여, 사용자가 왜 해당 경로가 가장 빠른지 쉽고 직관적으로 이해할 수 있도록 돕습니다.

## 🛠 2. 사용 기술 (Tech Stack)

| Category | Technologies |
| :--- | :--- |
| **Languages** | <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white"/> <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white"/> |
| **Frontend** | <img src="https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black"/> <img src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white"/> <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white"/> |
| **Backend** | <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white"/> <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white"/> |
| **Database & Cloud** | <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white"/> <img src="https://img.shields.io/badge/Amazon_RDS-527FFF?style=flat-square&logo=amazon-rds&logoColor=white"/> <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white"/> <img src="https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=white"/> |
| **AI & Data** | <img src="https://img.shields.io/badge/Pandas-150458?style=flat-square&logo=pandas&logoColor=white"/> <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white"/> <img src="https://img.shields.io/badge/XGBoost-110?style=flat-square"/> <img src="https://img.shields.io/badge/LightGBM-F3722C?style=flat-square"/> |
| **Tools** | <img src="https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white"/> <img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white"/> <img src="https://img.shields.io/badge/VS_Code-007ACC?style=flat-square&logo=visual-studio-code&logoColor=white"/> |

## 🧑‍🤝‍🧑 3. 팀원 및 역할 분담 (Team & Roles)

| 이름 | 담당 및 역할 (Role) | 주요 기여 내용 |
| :--- | :--- | :--- |
| **김경민**<br>(@kimgyeongmin5348) | **Frontend / Backend / Infra** | - KMA(기상청)/TOPIS 실시간 수집 스케줄러 및 전체 외부 API 연동 개발<br>- AWS EC2, RDS 인프라 구축 및 전체 데이터베이스 설계/관리<br>- FastAPI 백엔드 서버 및 React 프론트엔드 UI/UX 전체 구현<br>- LLM 챗봇 프롬프트 엔지니어링 및 모델 연동 |
| **인봉**<br>(@inBBong) | **Data & ML Engineering** | - OSRM 맵 매칭 및 경로 학습 데이터셋(OD 기반) 구축 파이프라인 개발<br>- XGBoost/LightGBM 기반 통행 소요 시간 및 교통량 예측 모델 학습<br>- ML 파이프라인 구축 및 머신러닝 모델 성능 튜닝 |

## 📂 4. 파일 구조 (Project Structure)
프로젝트는 크게 프론트엔드, 백엔드, 머신러닝 파이프라인, 데이터 수집 스크립트로 분리되어 관리됩니다.

```text
SEOUL_AI_TRAFFIC/
├── backend/            # FastAPI 백엔드 서버
│   ├── src/api/        # REST API 라우터 (경로 예측, 데이터 조회 등)
│   ├── src/db/         # 데이터베이스 스키마, 마이그레이션 및 ORM 모델
│   ├── src/services/   # ML/LLM 경로 예측 비즈니스 로직
│   └── src/workers/    # 실시간 데이터 수집 스케줄러 (APScheduler)
├── frontend/           # React 단일 페이지 애플리케이션 (Vite)
│   ├── src/pages/      # 대시보드, 경로 추천, 날씨, 챗봇 등 화면 컴포넌트
│   └── src/components/ # 공통 UI 및 지도(Kakao Map) / 차트 위젯
├── ml/                 # 머신러닝 모델 학습 파이프라인
│   ├── src/models/     # XGBoost, LightGBM 모델 학습 및 하이퍼파라미터 튜닝
│   └── artifacts/      # 학습이 완료된 최적 모델 파일(.joblib) 및 평가 리포트
├── scripts/            # 초기 데이터 구축 및 실시간 데이터 수집 수동 스크립트
├── data/               # 수집된 Raw 데이터 및 전처리된 학습 데이터셋 저장소
└── infra/              # 서버 인프라 및 배포 구성 파일
```

## 🏛 5. 기술 아키텍처 (System Architecture)

1. **데이터 수집 파이프라인**: 
   - `roadpulse-worker` 백그라운드 컨테이너가 APScheduler를 구동하여 주기적으로 서울시 TOPIS(도로 속도 및 돌발 상황) 및 KMA(기상청 날씨) 데이터를 수집합니다.
   - 수집된 데이터는 클라우드 **AWS RDS**에 실시간으로 적재됩니다.
2. **머신러닝(ML) 파이프라인**:
   - 적재된 과거 교통량 데이터를 바탕으로 `ml/` 디렉토리의 학습 파이프라인을 구동하여 모델을 평가 및 튜닝합니다.
   - 최적화된 모델은 `.joblib` 형태로 직렬화되어 백엔드 서버에서 서빙 가능한 상태로 관리됩니다.
3. **서비스 서빙 아키텍처**:
   - 사용자가 프론트엔드 웹에서 출발지 및 도착지를 입력하면, FastAPI 백엔드가 OSRM을 통해 기본 후보 경로들을 탐색합니다.
   - 탐색된 기본 경로들은 인메모리에 로드된 머신러닝 모델을 통해 '현재 교통 체증 페널티'가 계산되어 최적의 순서로 **재정렬(Ranking)**됩니다.
   - 랭킹된 최적 경로 데이터는 프론트엔드 지도 위젯(Kakao Maps API)에 시각화되어 제공됩니다.

## 🤖 6. AI 추론 방법 (AI Inference Method)

- **핵심 알고리즘**: Tree 기반 부스팅 모델 (`XGBoost`, `LightGBM`)
- **추론(Inference) 과정**:
  - 오프라인에서 학습되어 가장 성능이 높은(Best-saved) 모델이 `joblib`를 통해 백엔드 서버 가동 시 인메모리에 로드됩니다.
  - 사용자의 경로 추천 요청이 들어오면, 실시간으로 현재 시각, 기상 데이터, 휴일 여부, 과거 교통량 이동 평균(Rolling/Lag Feature)을 조합하여 즉각적인 추론용 피처(Feature)를 생성합니다.
  - 로드된 모델의 `predict()`를 호출하여 OSRM이 제시한 구간별로 **'예상 교통량 증가에 따른 통행 지연 시간'**을 예측합니다.
  - 이를 종합하여 각 경로의 실제 예상 소요 시간을 계산하고, 가장 빠르고 쾌적한 경로를 도출해냅니다.

## 💬 7. LLM 추론 방법 (LLM Inference Method)

- **사용 모델**: DeepSeek 계열 등 추론형(Reasoning) 거대 언어 모델 
- **서빙 방식**: NVIDIA NIM의 OpenAI 호환 API(`chat/completions`)를 통한 백엔드 서버 투 서버 통신 (API Key 클라이언트 노출 방지)
- **추론(Inference) 과정**:
  - ML 모델이 산출한 수치 데이터(경로별 예상 지연 시간, 교통 체증 페널티 비율, 모델 예측 신뢰도 등)를 그대로 프론트엔드에 노출하지 않고 백엔드에서 **LLM 프롬프트 컨텍스트**로 주입합니다.
  - 모델은 사용자에게 응답하기 전 내부적으로 **사고 과정(`reasoning_content`)**을 거쳐 복잡한 데이터를 분석합니다.
  - 최종적으로 "왜 이 경로가 다른 경로에 비해 덜 막히는지", "현재 날씨나 시간대가 경로에 어떤 영향을 미쳤는지"를 자연스럽고 친절한 문장으로 생성하여 챗봇 UI를 통해 제공합니다.

---

<details>
<summary><b>🛠 로컬 실행 가이드 (Getting Started)</b></summary>
<div markdown="1">

### 프로젝트 클론 및 패키지 설치
```bash
git clone https://github.com/your-repo/seoul-ai-traffic.git
cd seoul-ai-traffic

# 백엔드 의존성 설치 (uv 권장)
uv sync

# 프론트엔드 의존성 설치
cd frontend
npm install
```

### 서버 실행
```powershell
# 백엔드 서버 및 DB 연동 실행 (포트 8000)
uv run python main.py

# 프론트엔드 서버 실행 (포트 5173)
cd frontend
npm run dev
```
웹 브라우저에서 `http://localhost:5173/dashboard` 에 접속하여 서비스를 확인할 수 있습니다.

</div>
</details>

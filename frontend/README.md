# RoadPulse Frontend

서울시 교통·돌발·기상 데이터와 AI 예측을 한 화면에서 탐색하는 React UI입니다.
현재 화면의 수치는 UI 확인용 예시 데이터이며, 실제 API 연결은 다음 개발 단계에서 진행합니다.

## 개발 서버 실행

```powershell
cd C:\SEOUL_AI_TRAFFIC
pnpm --dir frontend dev
```

## 폴더 설정이 frontend로 되어 있다면 

```pnpm dev
```

브라우저에서 `http://localhost:5173`을 엽니다.

## 배포용 빌드 확인

```powershell
pnpm build
pnpm preview
```

미리보기 주소는 `http://localhost:4173`입니다.

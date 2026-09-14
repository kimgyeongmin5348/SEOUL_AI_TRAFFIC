# Route recommendation LLM

이 폴더는 교통량 예측이나 경로 선정을 수행하지 않습니다. 학습된 교통량 예측 AI가 추천한 경로에 대해 기본 경로시간, 예측 교통 증가 페널티, 후보 간 비교 점수와 예측 반영률을 근거로 사용자가 읽을 추천 사유만 생성합니다.

## 실행 흐름

```text
OSRM 후보 경로
  -> backend.services.route_prediction.predict_routes()
  -> 학습 모델로 후보별 교통량 및 비교 점수 계산
  -> 가장 낮은 유효 점수의 경로 선택
  -> backend.llm.route_explainer.explain_route_recommendation()
  -> NVIDIA LLM으로 선택 이유 작성
  -> 프론트엔드에 추천 결과와 설명 반환
```

LLM에는 모델의 원본 학습 Feature가 아니라 `예측 교통량`, `비교 점수`, `예측 반영률`, `기본 OSRM 시간`, `관측 시각`만 전달합니다. 따라서 학습 Feature나 모델 알고리즘이 바뀌어도 이 출력 계약이 유지되면 LLM 모듈은 변경하지 않습니다.

## 환경변수

기존 `backend/.env`를 그대로 사용합니다.

```dotenv
NVIDIA_LLM_MODEL=사용할_모델_ID
NVIDIA_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=발급받은_키
LLM_TIMEOUT_SECONDS=20
```

키는 프론트엔드나 별도 LLM용 `.env`로 복사하지 않습니다. LLM 설정이 없거나 호출에 실패하면 추천은 유지하고 근거 기반 템플릿 설명을 반환합니다.

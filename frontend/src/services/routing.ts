import type { PlaceSuggestion } from "../types/place"

export interface RouteResult {
  id: string
  label: string
  via: string
  time: number
  distance: number
  avgSpeed: number
  traffic: "원활" | "서행" | "혼잡"
  trafficLevel: "green" | "yellow" | "red"
  incidents: number
  weather: string
  delay: number
  ai: boolean
  reason: string | null
  coordinates: [number, number][]
  baseTime: number
  delayMin: number
  modelVersion?: string
  coverage?: number
  predictedVolume?: number | null
  score?: number
  trafficPenaltySec?: number
  incidentPenaltySec?: number
  speedPenaltySec?: number
  speedMatchRatio?: number
  speedObservedAt?: string | null
  incidentDetails?: RouteIncident[]
  linkMatchRatio?: number
  directionMatchRatio?: number | null
}

export interface RouteIncident {
  incident_id: string
  type: string
  category: string
  detail_type: string
  description: string | null
  impact_radius_m: number
}

interface OsrmRoute {
  distance: number
  duration: number
  geometry: { coordinates: [number, number][] }
  legs: { steps: { name: string; duration: number; distance: number; geometry?: { coordinates: [number, number][] } }[] }[]
}

interface ModelRanking {
  route_request_id?: string
  available: boolean
  model_version: string
  algorithm: string
  message: string
  target_at: string
  routes: {
    id: string
    ai: boolean
    coverage: number
    predicted_volume: number | null
    score: number
    base_duration_sec: number
    traffic_penalty_sec: number
    traffic_penalty_percent: number
    typical_volume: number | null
    predicted_vs_typical_percent: number | null
    distance_m: number | null
    incident_count: number
    incident_penalty_sec: number
    speed_penalty_sec: number
    speed_match_ratio: number
    link_match_ratio?: number
    direction_match_ratio?: number | null
    speed_observed_at: string | null
    incidents: RouteIncident[]
  }[]
  explanation?: {
    selected_route_id: string | null
    text: string
    source: "llm" | "template" | "system"
    llm_model: string | null
  }
}

function explainRouteChoice(
  route: { id: string; ai: boolean; coverage: number; predicted_volume: number | null; score: number } | undefined,
  allRoutes: ModelRanking["routes"],
  roadNames: string[],
  algorithm?: string,
) {
  if (!route) return null
  const coverage = Math.round(route.coverage * 100)
  const roads = roadNames.slice(0, 2).join("·") || "이 경로의 주요 도로"
  const recommended = allRoutes.find((item) => item.ai)
  const volume = route.predicted_volume == null ? "" : ` 시간당 평균 교통량은 약 ${Math.round(route.predicted_volume).toLocaleString("ko-KR")}대로 예측됐습니다.`

  if (route.ai) {
    const alternatives = allRoutes.filter((item) => item.id !== route.id && item.coverage >= 0.5)
    const next = alternatives.sort((a, b) => a.score - b.score)[0]
    const advantage = next && next.score > 0
      ? ` 다음 후보보다 혼잡 반영 비교 점수가 약 ${Math.max(1, Math.round((next.score - route.score) / next.score * 100))}% 유리합니다.`
      : " 비교 가능한 후보 중 혼잡 반영 점수가 가장 낮습니다."
    return `추천 이유: ${roads} 구간을 포함한 기본 소요시간에 최근 교통량과 기상 관측을 반영한 ${algorithm || "AI"} 결과입니다.${volume} 전체 경로의 ${coverage}%를 실제 관측 도로와 연결했고,${advantage} 이 점수는 경로 비교용이며 실제 도착시간 예측값은 아닙니다.`
  }

  if (recommended) {
    const gap = recommended.score > 0
      ? Math.max(0, Math.round((route.score - recommended.score) / recommended.score * 100))
      : 0
    return `${roads} 구간의 예측 반영률은 ${coverage}%입니다.${volume} AI 추천 경로보다 혼잡 반영 비교 점수가 ${gap}% 높아 대안 경로로 분류됐습니다.`
  }
  return `${roads} 구간 중 실제 관측 도로와 연결된 범위가 ${coverage}%입니다.${volume} 50% 이상인 후보가 없어 AI가 근거가 부족한 추천을 만들지 않았습니다.`
}

export async function getLiveSeoulRoutes(origin: PlaceSuggestion, dest: PlaceSuggestion, departureAt?: string) {
  const url = `https://router.project-osrm.org/route/v1/driving/${origin.lng},${origin.lat};${dest.lng},${dest.lat}?overview=full&alternatives=3&geometries=geojson&steps=true`
  const response = await fetch(url, { signal: AbortSignal.timeout(10000) })
  if (!response.ok) throw new Error("도로 경로를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
  const json = await response.json()
  const candidates: OsrmRoute[] = (json.routes || []).slice(0, 3)
  if (!candidates.length) throw new Error("출발지에서 목적지까지 주행 가능한 경로를 찾지 못했습니다.")
  const steps = candidates.map(r => r.legs.flatMap(leg => leg.steps))
  let ranking: ModelRanking | null = null
  let predictionMessage = ""
  try {
    const result = await fetch("/api/routes/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(45000),
      body: JSON.stringify({
        departure_at: departureAt,
        // 요청 로그(경로 학습 데이터셋)에 출발지·목적지를 남기기 위해 전달합니다.
        origin: { name: origin.name, lat: origin.lat, lng: origin.lng },
        destination: { name: dest.name, lat: dest.lat, lng: dest.lng },
        candidates: candidates.map((r, i) => ({
        id: String.fromCharCode(65 + i), duration_sec: r.duration,
        distance_m: r.distance,
        // 백엔드가 돌발 위치를 경로 polyline과 비교할 수 있게 전달합니다.
        coordinates: r.geometry.coordinates,
        steps: steps[i].map(step => ({
          name: step.name || "",
          duration_sec: step.duration,
          distance_m: step.distance,
          // OSRM step 기하를 전달해 백엔드가 링크 기하와 방위를 비교할 수 있게 합니다.
          coordinates: step.geometry?.coordinates ?? [],
        })),
        })),
      }),
    })
    const body = await result.json()
    if (!result.ok) throw new Error(typeof body.detail === "string" ? body.detail : "모델 추론 요청에 실패했습니다.")
    ranking = body as ModelRanking
    predictionMessage = `${ranking.algorithm} · ${ranking.model_version} · ${ranking.message}`
  } catch (err) {
    predictionMessage = `${err instanceof Error ? err.message : "모델 서버에 연결할 수 없습니다."} OSRM 기본 경로만 표시합니다.`
  }
  const routes: RouteResult[] = candidates.map((r, i) => {
    const id = String.fromCharCode(65 + i)
    const prediction = ranking?.routes.find(item => item.id === id)
    const ai = Boolean(ranking?.available && prediction?.ai)
    const names = [...new Set(steps[i].map(s => s.name).filter(Boolean))]

    // 실시간 도로 속도(speed_penalty), AI 교통량 지연(traffic_penalty), 사고(incident_penalty)가 결합된 최종 소요시간
    const baseDurationSec = r.duration
    const effectiveDurationSec = prediction?.score && prediction.score > 0 ? prediction.score : baseDurationSec
    const time = Math.max(1, Math.round(effectiveDurationSec / 60))
    const baseTime = Math.max(1, Math.round(baseDurationSec / 60))
    const delayMin = Math.max(0, Math.round((effectiveDurationSec - baseDurationSec) / 60))
    const avgSpeed = Math.round((r.distance / Math.max(1, effectiveDurationSec)) * 3.6)

    const trafficLevel: "green" | "yellow" | "red" =
      avgSpeed < 25 ? "red" : avgSpeed < 45 ? "yellow" : "green"
    const traffic: "원활" | "서행" | "혼잡" =
      trafficLevel === "red" ? "혼잡" : trafficLevel === "yellow" ? "서행" : "원활"

    return {
      id, label: `Route ${id}${ai ? " (AI 추천)" : ""}`,
      via: names.slice(0, 4).join(" / ") || "도로명 정보 없음",
      time,
      baseTime,
      distance: Number((r.distance / 1000).toFixed(1)),
      avgSpeed,
      traffic,
      trafficLevel,
      incidents: prediction?.incident_count || 0,
      weather: "미연동",
      delay: delayMin,
      delayMin,
      ai,
      reason: ranking?.explanation?.selected_route_id === id
        ? ranking.explanation.text
        : explainRouteChoice(prediction, ranking?.routes || [], names, ranking?.algorithm),
      coordinates: r.geometry.coordinates.map(([lng, lat]) => [lat, lng]),
      modelVersion: ranking?.model_version,
      coverage: prediction?.coverage,
      predictedVolume: prediction?.predicted_volume,
      score: prediction?.score,
      trafficPenaltySec: prediction?.traffic_penalty_sec,
      incidentPenaltySec: prediction?.incident_penalty_sec,
      speedPenaltySec: prediction?.speed_penalty_sec,
      speedMatchRatio: prediction?.speed_match_ratio,
      speedObservedAt: prediction?.speed_observed_at,
      incidentDetails: prediction?.incidents,
      linkMatchRatio: prediction?.link_match_ratio,
      directionMatchRatio: prediction?.direction_match_ratio,
    }
  })
  return { origin, dest, routes, predictionMessage }
}

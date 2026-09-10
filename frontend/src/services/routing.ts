// 서울 25개 구 및 주요 랜드마크 좌표 사전
export const SEOUL_GEO_COORDS: Record<string, [number, number]> = {
  "합정": [37.5495, 126.9138],
  "합정동": [37.5495, 126.9138],
  "마포": [37.5458, 126.9525],
  "마포구": [37.5458, 126.9525],
  "홍대": [37.5563, 126.9226],
  "홍대입구": [37.5563, 126.9226],
  "신촌": [37.5552, 126.9368],
  "여의도": [37.5255, 126.9242],
  "여의도동": [37.5255, 126.9242],
  "영등포": [37.5180, 126.9070],
  "영등포구": [37.5180, 126.9070],
  "강남": [37.4979, 127.0276],
  "강남역": [37.4979, 127.0276],
  "강남구": [37.4979, 127.0276],
  "역삼": [37.5006, 127.0365],
  "역삼동": [37.5006, 127.0365],
  "테헤란로": [37.5040, 127.0450],
  "선릉": [37.5045, 127.0490],
  "삼성": [37.5088, 127.0632],
  "잠실": [37.5133, 127.1001],
  "잠실동": [37.5133, 127.1001],
  "송파구": [37.5048, 127.1145],
  "서초": [37.4919, 127.0078],
  "서초동": [37.4919, 127.0078],
  "서초구": [37.4919, 127.0078],
  "양재": [37.4841, 127.0346],
  "양재동": [37.4841, 127.0346],
  "종로": [37.5704, 126.9922],
  "종로구": [37.5704, 126.9922],
  "광화문": [37.5759, 126.9768],
  "시청": [37.5665, 126.9780],
  "서울역": [37.5547, 126.9706],
  "용산": [37.5326, 126.9900],
  "용산구": [37.5326, 126.9900],
  "이태원": [37.5345, 126.9940],
  "성수": [37.5446, 127.0559],
  "성동구": [37.5509, 127.0410],
  "동대문": [37.5714, 127.0097],
  "동대문구": [37.5838, 127.0507],
  "중랑구": [37.5953, 127.0939],
  "성북구": [37.6069, 127.0232],
  "강북구": [37.6469, 127.0147],
  "도봉구": [37.6658, 127.0317],
  "노원구": [37.6542, 127.0770],
  "상계동": [37.6580, 127.0700],
  "은평구": [37.6176, 126.9227],
  "서대문구": [37.5833, 126.9356],
  "양천구": [37.5270, 126.8560],
  "목동": [37.5300, 126.8650],
  "강서구": [37.5612, 126.8228],
  "김포공항": [37.5586, 126.7944],
  "구로구": [37.4954, 126.8581],
  "신도림": [37.5088, 126.8912],
  "신도림동": [37.5088, 126.8912],
  "금천구": [37.4600, 126.9001],
  "가산디지털단지": [37.4815, 126.8826],
  "동작구": [37.4971, 126.9443],
  "노량진": [37.5135, 126.9410],
  "관악구": [37.4653, 126.9438],
  "서울대입구": [37.4812, 126.9527],
  "사당": [37.4765, 126.9816],
  "강동구": [37.5502, 127.1470],
  "천호": [37.5385, 127.1235],
  "광진구": [37.5481, 127.0857],
  "건대입구": [37.5404, 127.0692],
}

// 텍스트 주소에서 위경도 찾기
export function geocodeSeoulAddress(addr: string): { name: string; lat: number; lng: number } {
  const gps = /^현 위치 \((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)$/.exec(addr.trim())
  if (gps) {
    const lat = Number(gps[1])
    const lng = Number(gps[2])
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) throw new Error("위치 좌표가 올바르지 않습니다.")
    return { name: "현 위치", lat, lng }
  }
  const clean = addr.trim().toLowerCase()
  for (const [key, [lat, lng]] of Object.entries(SEOUL_GEO_COORDS)) {
    if (clean.includes(key.toLowerCase()) || key.toLowerCase().includes(clean)) {
      return { name: addr, lat, lng }
    }
  }
  throw new Error(`"${addr}" 위치를 찾지 못했습니다. 지원하는 서울 지명 또는 현 위치를 사용해 주세요.`)
}

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
  modelVersion?: string
  coverage?: number
  predictedVolume?: number | null
}

interface OsrmRoute {
  distance: number
  duration: number
  geometry: { coordinates: [number, number][] }
  legs: { steps: { name: string; duration: number }[] }[]
}

interface ModelRanking {
  available: boolean
  model_version: string
  algorithm: string
  message: string
  target_at: string
  routes: { id: string; ai: boolean; coverage: number; predicted_volume: number | null; score: number }[]
}

export async function getLiveSeoulRoutes(originText: string, destText: string, departureAt?: string) {
  const origin = geocodeSeoulAddress(originText)
  const dest = geocodeSeoulAddress(destText)
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
      body: JSON.stringify({ departure_at: departureAt, candidates: candidates.map((r, i) => ({
        id: String.fromCharCode(65 + i), duration_sec: r.duration,
        steps: steps[i].map(step => ({ name: step.name || "", duration_sec: step.duration })),
      })) }),
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
    return {
      id, label: `Route ${id}${ai ? " (AI 추천)" : ""}`,
      via: names.slice(0, 4).join(" / ") || "도로명 정보 없음",
      time: Math.max(1, Math.round(r.duration / 60)),
      distance: Number((r.distance / 1000).toFixed(1)),
      avgSpeed: Math.round(r.distance / r.duration * 3.6),
      traffic: "원활", trafficLevel: "green", incidents: 0, weather: "미연동", delay: 0,
      ai,
      reason: prediction ? `${ranking?.algorithm} 교통량 예측 반영 ${Math.round(prediction.coverage * 100)}% · 전일 동시간 대비 증가율로 경로 평가 (주행시간 직접 예측 아님)` : null,
      coordinates: r.geometry.coordinates.map(([lng, lat]) => [lat, lng]),
      modelVersion: ranking?.model_version, coverage: prediction?.coverage,
      predictedVolume: prediction?.predicted_volume,
    }
  })
  return { origin, dest, routes, predictionMessage }
}

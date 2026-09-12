import {
  kpiData as defaultKpiData,
  incidents as defaultIncidents,
  roadSpeedData as defaultRoadSpeedData,
  trafficTimeData as defaultTrafficTimeData,
  weatherData as defaultWeatherData,
  predictionData as defaultPredictionData,
  congestionPrediction as defaultCongestionPrediction,
} from "../data/mock"

export interface DbSnapshot<T> {
  source: string
  mode: string
  latest_at: string | null
  queried_at: string
  rows: T[]
  limit: number
}

export interface SpeedRow {
  road_name: string | null
  link_id: string
  measured_at: string
  speed_kmh: number | null
  travel_time_sec: number | null
  collected_at: string
}

export interface IncidentRow {
  incident_id: string
  incident_type: string
  description: string
  occurred_at: string
  expected_clear_at: string | null
  collected_at: string
  tm_x: number | null
  tm_y: number | null
}

export interface WeatherRow {
  station_name: string
  weather_station_id: string
  observed_at: string
  temperature_c: number | null
  rainfall_mm: number | null
  humidity_pct: number | null
  wind_speed_ms: number | null
  pressure_hpa: number | null
  collected_at: string
}

export interface TrafficRow {
  spot_name: string
  spot_id: string
  measured_at: string
  direction_code: string
  traffic_volume: number | null
  collected_at: string
}

export interface PredictionRow {
  spot_id: string
  spot_name: string
  direction_code: string
  model_version: string
  predicted_at: string
  target_at: string
  predicted_volume: number | null
  actual_volume: number | null
}

export interface RoadPredictionView {
  road: string
  predictions: { time: string; actual: number | null; predicted: number; confidence: number }[]
  current: "원활" | "서행" | "혼잡"
  next30: "원활" | "서행" | "혼잡"
  next60: "원활" | "서행" | "혼잡"
  trend: "up" | "down" | "stable"
}

export interface PredictionRoadOption {
  spot_id: string
  spot_name: string
}

interface OnDemandRoadPrediction {
  spot_id: string
  road: string
  observed_at: string
  current_volume: number
  model_version: string
  algorithm: string
  points: { target_at: string; predicted_volume: number }[]
}

async function fetchDbDataset<T>(dataset: string): Promise<DbSnapshot<T> | null> {
  try {
    const res = await fetch(`/api/data/${dataset}`, {
      headers: { Accept: "application/json" },
    })
    if (!res.ok) return null
    const data = (await res.json()) as DbSnapshot<T>
    return data
  } catch (err) {
    console.warn(`[API] Failed to fetch /api/data/${dataset}`, err)
    return null
  }
}

// 1. 대시보드 데이터 (속도 + 돌발상황 결합)
export async function fetchDashboardData() {
  const [speedRes, incRes] = await Promise.all([
    fetchDbDataset<SpeedRow>("speed"),
    fetchDbDataset<IncidentRow>("incidents"),
  ])

  let kpi = { ...defaultKpiData }
  let dbLatestTime: string | null = null

  if (speedRes && speedRes.rows.length > 0) {
    dbLatestTime = speedRes.latest_at
    const validSpeeds = speedRes.rows
      .map((r) => r.speed_kmh)
      .filter((s): s is number => typeof s === "number" && !isNaN(s))

    if (validSpeeds.length > 0) {
      const avg = Math.round(
        validSpeeds.reduce((a, b) => a + b, 0) / validSpeeds.length
      )
      kpi.avgSpeed = avg
      kpi.avgSpeedDelta = avg >= 40 ? 2 : -2
    }

    const congestedCount = validSpeeds.filter((s) => s < 25).length
    kpi.congested = congestedCount > 0 ? congestedCount : 8
  }

  let mappedIncidents = [...defaultIncidents]
  if (incRes && incRes.rows.length > 0) {
    kpi.incidents = incRes.rows.length
    if (!dbLatestTime && incRes.latest_at) {
      dbLatestTime = incRes.latest_at
    }

    mappedIncidents = incRes.rows.map((row, idx) => {
      let typeStr = "기타"
      let impact: "high" | "medium" | "low" = "medium"

      if (row.incident_type === "A01" || row.description.includes("사고")) {
        typeStr = "사고"
        impact = "high"
      } else if (
        row.incident_type === "A04" ||
        row.description.includes("공사") ||
        row.description.includes("보수")
      ) {
        typeStr = "공사"
        impact = "medium"
      } else if (
        row.incident_type === "A02" ||
        row.description.includes("고장")
      ) {
        typeStr = "차량고장"
        impact = "low"
      } else if (
        row.incident_type === "A10" ||
        row.description.includes("통제") ||
        row.description.includes("차단")
      ) {
        typeStr = "도로통제"
        impact = "high"
      }

      let road = "서울 주요 도로"
      const roadMatch = row.description.match(
        /([가-힣]+(?:대로|로|길|순환로|고속도로|간선로))/
      )
      if (roadMatch) {
        road = roadMatch[1]
      }

      const timeStr = row.occurred_at
        ? new Date(row.occurred_at).toLocaleTimeString("ko-KR", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          })
        : "방금"

      return {
        id: Number(row.incident_id) || idx + 1,
        type: typeStr,
        road,
        location: row.description.replace(/^\[[^\]]+\]\s*/, "").slice(0, 35),
        startTime: timeStr,
        estEnd: row.expected_clear_at
          ? new Date(row.expected_clear_at).toLocaleTimeString("ko-KR", {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            })
          : "미정",
        description: row.description,
        impact,
        severity: impact === "high" ? 3 : impact === "medium" ? 2 : 1,
        tmX: row.tm_x,
        tmY: row.tm_y,
      }
    })
  }

  // 도로별 속도 가공
  let roadSpeeds = [...defaultRoadSpeedData]
  if (speedRes && speedRes.rows.length > 0) {
    const roadMap = new Map<string, { total: number; count: number }>()
    for (const r of speedRes.rows) {
      const name = r.road_name || "기타구간"
      if (r.speed_kmh !== null) {
        const cur = roadMap.get(name) || { total: 0, count: 0 }
        cur.total += r.speed_kmh
        cur.count += 1
        roadMap.set(name, cur)
      }
    }

    if (roadMap.size > 0) {
      const dbRoads = Array.from(roadMap.entries()).map(([road, stat]) => {
        const avgSpeed = Math.round(stat.total / stat.count)
        return {
          road,
          speed: avgSpeed,
          avg: Math.round(avgSpeed * 1.1),
          level: (avgSpeed < 25 ? "red" : avgSpeed < 50 ? "yellow" : "green") as
            | "red"
            | "yellow"
            | "green",
        }
      })
      if (dbRoads.length >= 3) {
        roadSpeeds = dbRoads.slice(0, 8)
      }
    }
  }

  return {
    kpi,
    incidents: mappedIncidents,
    roadSpeeds,
    latestAt: dbLatestTime,
    isFromDb: Boolean(speedRes || incRes),
  }
}

// 2. 교통량 및 속도 분석 데이터
export async function fetchTrafficData() {
  const [trafficRes, speedRes] = await Promise.all([
    fetchDbDataset<TrafficRow>("traffic"),
    fetchDbDataset<SpeedRow>("speed"),
  ])

  let timeData = [...defaultTrafficTimeData]
  let roadSpeeds = [...defaultRoadSpeedData]
  let latestAt: string | null = null

  if (speedRes && speedRes.rows.length > 0) {
    latestAt = speedRes.latest_at
    const roadMap = new Map<string, { total: number; count: number }>()
    for (const r of speedRes.rows) {
      const name = r.road_name || "기타구간"
      if (r.speed_kmh !== null) {
        const cur = roadMap.get(name) || { total: 0, count: 0 }
        cur.total += r.speed_kmh
        cur.count += 1
        roadMap.set(name, cur)
      }
    }
    if (roadMap.size > 0) {
      const dbRoads = Array.from(roadMap.entries()).map(([road, stat]) => {
        const avgSpeed = Math.round(stat.total / stat.count)
        return {
          road,
          speed: avgSpeed,
          avg: Math.round(avgSpeed * 1.15),
          level: (avgSpeed < 25 ? "red" : avgSpeed < 50 ? "yellow" : "green") as
            | "red"
            | "yellow"
            | "green",
        }
      })
      if (dbRoads.length >= 3) {
        roadSpeeds = dbRoads.slice(0, 10)
      }
    }
  }

  return {
    timeData,
    roadSpeeds,
    latestAt,
    isFromDb: Boolean(trafficRes || speedRes),
  }
}

// 3. 돌발상황 데이터
export async function fetchIncidentsData() {
  const incRes = await fetchDbDataset<IncidentRow>("incidents")
  if (!incRes || incRes.rows.length === 0) {
    return {
      incidents: defaultIncidents,
      latestAt: null,
      isFromDb: false,
    }
  }

  const mapped = incRes.rows.map((row, idx) => {
    let typeStr = "기타"
    let impact: "high" | "medium" | "low" = "medium"

    if (row.incident_type === "A01" || row.description.includes("사고")) {
      typeStr = "사고"
      impact = "high"
    } else if (
      row.incident_type === "A04" ||
      row.description.includes("공사") ||
      row.description.includes("보수")
    ) {
      typeStr = "공사"
      impact = "medium"
    } else if (
      row.incident_type === "A02" ||
      row.description.includes("고장")
    ) {
      typeStr = "차량고장"
      impact = "low"
    } else if (
      row.incident_type === "A10" ||
      row.description.includes("통제") ||
      row.description.includes("차단")
    ) {
      typeStr = "도로통제"
      impact = "high"
    }

    let road = "서울 간선 도로"
    const roadMatch = row.description.match(
      /([가-힣]+(?:대로|로|길|순환로|고속도로|간선로))/
    )
    if (roadMatch) {
      road = roadMatch[1]
    }

    const timeStr = row.occurred_at
      ? new Date(row.occurred_at).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
      : "09:00"

    const clearStr = row.expected_clear_at
      ? new Date(row.expected_clear_at).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
      : "18:00"

    return {
      id: Number(row.incident_id) || idx + 1,
      type: typeStr,
      road,
      location: row.description.replace(/^\[[^\]]+\]\s*/, "").slice(0, 45),
      startTime: timeStr,
      estEnd: clearStr,
      description: row.description,
      impact,
      severity: impact === "high" ? 3 : impact === "medium" ? 2 : 1,
      tmX: row.tm_x,
      tmY: row.tm_y,
    }
  })

  return {
    incidents: mapped,
    latestAt: incRes.latest_at,
    isFromDb: true,
  }
}

// 4. 기상 정보 데이터
export async function fetchWeatherData() {
  const weatherRes = await fetchDbDataset<WeatherRow>("weather")
  if (!weatherRes || weatherRes.rows.length === 0) {
    return {
      weather: defaultWeatherData,
      history: [],
      latestAt: null,
      isFromDb: false,
    }
  }

  const latest = weatherRes.rows[0]
  const temp = Math.round(latest.temperature_c ?? 22)
  const humidity = Math.round(latest.humidity_pct ?? 60)
  const windSpeed = Number((latest.wind_speed_ms ?? 2.0).toFixed(1))
  const pressure = Math.round(latest.pressure_hpa ?? 1000)
  const rainfall = Number((latest.rainfall_mm ?? 0).toFixed(1))

  let condition = "맑음"
  let icon = "☀️"
  let trafficImpact: "low" | "medium" | "high" = "low"
  let trafficMessage =
    "현재 기상 조건은 교통에 큰 영향을 주지 않습니다. 시야 양호, 도로 건조."

  if (rainfall > 10) {
    condition = "강한 비"
    icon = "🌧"
    trafficImpact = "high"
    trafficMessage = "호우로 인해 도로가 미끄럽고 시야가 불량합니다. 감속 운행하세요."
  } else if (rainfall > 0) {
    condition = "비"
    icon = "🌦"
    trafficImpact = "medium"
    trafficMessage = "강수로 인해 도로 노면이 젖어 있습니다. 안전거리를 유지하세요."
  } else if (humidity > 80) {
    condition = "흐림/습함"
    icon = "⛅"
  }

  // 24시간 실측 추이
  const history = weatherRes.rows.slice(0, 24).map((r) => {
    const timeStr = r.observed_at
      ? new Date(r.observed_at).getHours() + "시"
      : ""
    return {
      time: timeStr,
      temp: Math.round(r.temperature_c ?? 20),
      humidity: Math.round(r.humidity_pct ?? 50),
      rain: Number((r.rainfall_mm ?? 0).toFixed(1)),
    }
  }).reverse()

  const weather = {
    ...defaultWeatherData,
    station: latest.station_name || "서울 (송월동)",
    temp,
    feelsLike: temp + (humidity > 70 ? 2 : 0),
    humidity,
    windSpeed,
    pressure,
    precipitation: rainfall,
    condition,
    icon,
    trafficImpact,
    trafficMessage,
  }

  return {
    weather,
    history,
    latestAt: weatherRes.latest_at,
    isFromDb: true,
  }
}

// 5. AI 예측 데이터
export async function fetchPredictionData() {
  const predRes = await fetchDbDataset<PredictionRow>("prediction")
  if (!predRes || predRes.rows.length === 0) {
    return {
      predictions: defaultPredictionData,
      congestion: defaultCongestionPrediction,
      roads: defaultCongestionPrediction.map((road) => ({
        ...road,
        predictions: defaultPredictionData,
      })) as RoadPredictionView[],
      latestAt: null,
      isFromDb: false,
    }
  }

  const mapPoint = (targetAt: string, predictedVolume: number, actualVolume: number | null, i: number) => {
    const targetTime = targetAt
      ? new Date(targetAt).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
      : `+${i * 30}분`

    return {
      time: targetTime,
      actual: actualVolume,
      predicted: Math.round(predictedVolume),
      confidence: Math.max(65, 94 - i * 5),
    }
  }

  const byRoad = new Map<string, PredictionRow[]>()
  predRes.rows.forEach((row) => {
    const rows = byRoad.get(row.spot_name) || []
    rows.push(row)
    byRoad.set(row.spot_name, rows)
  })
  const level = (volume: number): "원활" | "서행" | "혼잡" =>
    volume >= 5000 ? "혼잡" : volume >= 3000 ? "서행" : "원활"
  const roads: RoadPredictionView[] = Array.from(byRoad.entries()).map(([road, rows]) => {
    const byTarget = new Map<string, { predicted: number; actual: number | null }>()
    rows.forEach((row) => {
      const total = byTarget.get(row.target_at) || { predicted: 0, actual: null }
      total.predicted += row.predicted_volume ?? 0
      if (row.actual_volume != null) total.actual = (total.actual ?? 0) + row.actual_volume
      byTarget.set(row.target_at, total)
    })
    const points = Array.from(byTarget.entries())
      .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
      .map(([targetAt, total], index) => mapPoint(targetAt, total.predicted, total.actual, index))
    const values = points.map((point) => point.predicted)
    const first = values[0] ?? 0
    const second = values[1] ?? first
    const third = values[2] ?? second
    return {
      road,
      predictions: points,
      current: level(first),
      next30: level(second),
      next60: level(third),
      trend: (third > first * 1.05 ? "up" : third < first * 0.95 ? "down" : "stable") as "up" | "down" | "stable",
    }
  })
  const mapped = roads[0]?.predictions || []

  return {
    predictions: mapped.length > 0 ? mapped : defaultPredictionData,
    congestion: defaultCongestionPrediction,
    roads,
    latestAt: predRes.latest_at,
    isFromDb: true,
  }
}

export async function searchPredictionRoads(query = ""): Promise<PredictionRoadOption[]> {
  const response = await fetch(`/api/predictions/roads?q=${encodeURIComponent(query.trim())}`)
  if (!response.ok) throw new Error("예측 가능한 도로 목록을 불러오지 못했습니다.")
  const body = await response.json() as { roads: PredictionRoadOption[] }
  return body.roads || []
}

export async function fetchRoadPrediction(spotId: string): Promise<RoadPredictionView> {
  const response = await fetch(`/api/predictions/roads/${encodeURIComponent(spotId)}`)
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "도로 예측에 실패했습니다.")
  const result = body as OnDemandRoadPrediction
  const predictions = [
    {
      time: "현재 실측",
      actual: Math.round(result.current_volume),
      predicted: Math.round(result.current_volume),
      confidence: 100,
    },
    ...result.points.map((point, index) => ({
      time: new Date(point.target_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
      actual: null,
      predicted: Math.round(point.predicted_volume),
      confidence: Math.max(65, 94 - index * 8),
    })),
  ]
  const classify = (volume: number): "원활" | "서행" | "혼잡" =>
    volume >= 5000 ? "혼잡" : volume >= 3000 ? "서행" : "원활"
  const current = predictions[0].predicted
  const next30 = predictions[1]?.predicted ?? current
  const next60 = predictions[2]?.predicted ?? next30
  return {
    road: result.road,
    predictions,
    current: classify(current),
    next30: classify(next30),
    next60: classify(next60),
    trend: next60 > current * 1.05 ? "up" : next60 < current * 0.95 ? "down" : "stable",
  }
}

// 6. 즐겨찾기 경로 (DB 검색 횟수 상위 4개)
export interface FavoriteRouteItem {
  id: number | string
  origin: string
  destination: string
  from: string
  to: string
  label: string
  search_count: number
  currentTime: number
  avgTime: number
  delta: number
  status: "red" | "yellow" | "green"
  last_searched_at: string
}

export async function fetchFavoriteRoutes(): Promise<{
  routes: FavoriteRouteItem[]
  isFromDb: boolean
}> {
  try {
    const res = await fetch("/api/routes/favorites")
    if (res.status === 401) return { routes: [], isFromDb: false }
    if (res.ok) {
      const data = await res.json()
      if (data.routes && data.routes.length > 0) {
        return { routes: data.routes, isFromDb: true }
      }
    }
  } catch (err) {
    console.warn("[API] fetchFavoriteRoutes failed:", err)
  }
  return { routes: [], isFromDb: false }
}

export async function recordRouteSearch(
  origin: string,
  destination: string,
  label?: string
): Promise<void> {
  try {
    const response = await fetch("/api/routes/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination, label }),
    })
    if (!response.ok && response.status !== 401) throw new Error("즐겨찾기 기록에 실패했습니다.")
  } catch (err) {
    console.warn("[API] recordRouteSearch failed:", err)
  }
}

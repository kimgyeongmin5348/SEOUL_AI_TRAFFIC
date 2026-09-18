import { useState, useEffect } from "react"
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import {
  fetchRoadPrediction,
  searchPredictionRoads,
  PredictionRoadOption,
  RoadPredictionView,
} from "../services/api"

const trendColor = { up: "#ff3b30", down: "#34c759", stable: "#007aff" }
const trendIcon = { up: "↑", down: "↓", stable: "→" }
const levelBg = {
  원활: { bg: "rgba(52,199,89,0.12)", text: "#34c759" },
  서행: { bg: "rgba(255,149,0,0.12)", text: "#ff9500" },
  혼잡: { bg: "rgba(255,59,48,0.12)", text: "#ff3b30" },
}

export default function Prediction() {
  const [horizon, setHorizon] = useState("+1시간")
  const [roadQuery, setRoadQuery] = useState("")
  const [selectedRoad, setSelectedRoad] = useState("")
  const [roadOptions, setRoadOptions] = useState<PredictionRoadOption[]>([])
  const [roadLoading, setRoadLoading] = useState(false)
  const [roadError, setRoadError] = useState("")
  const [loading, setLoading] = useState(true)
  const [predState, setPredState] = useState<{
    predictions: Array<{ time: string; actual: number | null; predicted: number; confidence: number }>
    congestion: Array<any>
    latestAt: string | null
    isFromDb: boolean
    roads: RoadPredictionView[]
  }>({
    predictions: [],
    congestion: [],
    latestAt: null,
    isFromDb: false,
    roads: [],
  })

  useEffect(() => {
    let active = true
    setLoading(true)
    searchPredictionRoads("")
      .then(async (roads) => {
        if (!active) return
        setRoadOptions(roads)
        if (roads.length > 0) {
          try {
            const firstRoad = roads[0]
            const prediction = await fetchRoadPrediction(firstRoad.spot_id)
            if (active) {
              setSelectedRoad(prediction.road)
              setPredState({
                predictions: prediction.predictions,
                congestion: [],
                latestAt: null,
                isFromDb: true,
                roads: [prediction],
              })
            }
          } catch (e) {
            console.warn(e)
          }
        }
      })
      .catch((err) => {
        console.warn(err)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      searchPredictionRoads(roadQuery === selectedRoad ? "" : roadQuery)
        .then((roads) => {
          if (active) setRoadOptions(roads)
        })
        .catch(() => {
          if (active) setRoadOptions([])
        })
    }, roadQuery ? 220 : 0)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [roadQuery, selectedRoad])

  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener("resize", checkMobile)
    return () => window.removeEventListener("resize", checkMobile)
  }, [])

  const activeRoad =
    predState.roads.find((item) => item.road === selectedRoad) ||
    predState.roads[0]
  const predictionData = activeRoad?.predictions || predState.predictions
  const congestionPrediction = predState.roads

  const selectRoad = async (option: PredictionRoadOption) => {
    setRoadLoading(true)
    setRoadError("")
    setRoadQuery(option.spot_name)
    try {
      const prediction = await fetchRoadPrediction(option.spot_id)
      setPredState((state) => ({
        ...state,
        isFromDb: true,
        predictions: prediction.predictions,
        roads: [
          prediction,
          ...state.roads.filter((item) => item.road !== prediction.road),
        ],
      }))
      setSelectedRoad(prediction.road)
    } catch (err) {
      setRoadError(
        err instanceof Error ? err.message : "도로 예측에 실패했습니다."
      )
    } finally {
      setRoadLoading(false)
    }
  }

  return (
    <div className="min-h-full flex relative" style={{ minHeight: "100dvh" }}>
      <SubpageBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 md:pl-28 md:pr-8 px-3 sm:px-6 pb-24 md:pb-8 pt-[max(64px,calc(env(safe-area-inset-top)+56px))] md:pt-6 max-w-7xl mx-auto w-full">
        <div className="animate-slide-up">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1">
            <div>
              <h1
                className="text-white text-xl sm:text-2xl font-bold tracking-tight"
                style={{
                  fontFamily: "var(--font-display)",
                  textShadow: "0 2px 12px rgba(0,0,0,0.35)",
                }}
              >
                AI 예측
              </h1>
              <p
                className="text-white/70 text-sm mt-0.5"
                style={{ fontFamily: "var(--font-body)" }}
              >
                AI 타임머신 기반 특정 도로 미래 통과 속도 예측 · 최대 3시간
              </p>
            </div>
            {predState.isFromDb && (
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium"
                style={{
                  background: "rgba(52,199,89,0.2)",
                  color: "#34c759",
                  border: "1px solid rgba(52,199,89,0.3)",
                  fontFamily: "var(--font-body)",
                }}
              >
                <div className="w-1.5 h-1.5 rounded-full pulse-dot bg-[#34c759]" />
                DB 학습 모델 · 신뢰도 {predictionData[0]?.confidence ?? 92}%
              </div>
            )}
          </div>
        </div>

        <div
          className="glass p-3 mt-4 animate-slide-up-delay-1"
          style={{ borderRadius: 18 }}
        >
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <input
                value={roadQuery}
                onChange={(event) => setRoadQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && roadOptions[0])
                    void selectRoad(roadOptions[0])
                }}
                placeholder="예측할 도로 검색 (예: 강남대로, 종로, 성산로)"
                className="w-full rounded-2xl bg-white/60 border border-white/80 px-4 py-3 text-base sm:text-sm outline-none focus:ring-2 focus:ring-[#007aff]/30"
              />
              {roadQuery.trim() && roadQuery !== selectedRoad && (
                <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-30 glass rounded-2xl p-1.5 shadow-xl max-h-56 overflow-y-auto">
                  {roadOptions.slice(0, 8).map((item) => (
                    <button
                      key={item.spot_id}
                      type="button"
                      onClick={() => void selectRoad(item)}
                      className="interactive-control w-full text-left px-3 py-2 rounded-xl text-sm text-[#33334d] hover:bg-white/70"
                    >
                      {item.spot_name}
                    </button>
                  ))}
                  {!roadOptions.length && (
                    <p className="px-3 py-3 text-xs text-[#6b6b8a]">
                      예측 가능한 측정 도로가 없습니다.
                    </p>
                  )}
                </div>
              )}
            </div>
            <button
              type="button"
              disabled={!roadOptions.length || roadLoading}
              onClick={() => roadOptions[0] && void selectRoad(roadOptions[0])}
              className="interactive-control button-glide px-5 py-3 rounded-2xl text-sm font-semibold text-white disabled:opacity-40 cursor-pointer shrink-0"
              style={{ background: "linear-gradient(135deg,#007aff,#5e5ce6)" }}
            >
              {roadLoading ? "AI 예측 중…" : "도로 예측 보기"}
            </button>
          </div>
          {roadOptions.length > 0 && (
            <div className="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-black/5 overflow-x-auto no-scrollbar pb-1">
              <span className="text-[11px] text-[#6b6b8a] py-1 whitespace-nowrap font-medium shrink-0">
                측정 지점
              </span>
              {roadOptions.slice(0, 6).map((item) => {
                const isSelected = item.spot_name === selectedRoad
                return (
                  <button
                    key={item.spot_id}
                    type="button"
                    onClick={() => void selectRoad(item)}
                    className="interactive-control px-3 py-1 rounded-xl text-xs whitespace-nowrap cursor-pointer transition-all duration-200"
                    style={{
                      background: isSelected
                        ? "linear-gradient(135deg, #2563eb, #38bdf8)"
                        : "rgba(0, 0, 0, 0.05)",
                      color: isSelected ? "#ffffff" : "#4a4a68",
                      fontWeight: isSelected ? 600 : 500,
                      boxShadow: isSelected
                        ? "0 2px 8px rgba(37, 99, 235, 0.35)"
                        : "none",
                    }}
                  >
                    {item.spot_name}
                  </button>
                )
              })}
            </div>
          )}
          {roadError && (
            <p role="alert" className="mt-2 text-xs text-red-600">
              {roadError}
            </p>
          )}
        </div>

        {loading ? (
          <div
            className="glass p-12 text-center flex flex-col items-center justify-center gap-3 my-8 animate-pulse"
            style={{ borderRadius: 20 }}
          >
            <div className="w-8 h-8 rounded-full border-2 border-[#5e5ce6] border-t-transparent animate-spin" />
            <p
              className="text-white/80 text-sm font-medium"
              style={{ fontFamily: "var(--font-body)" }}
            >
              AI 모델 실시간 예측 결과를 불러오는 중입니다...
            </p>
          </div>
        ) : predictionData.length === 0 ? (
          <div className="glass p-12 text-center my-8" style={{ borderRadius: 20 }}>
            <p
              className="text-white/80 text-base font-semibold mb-1"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DB에 저장된 도로 예측 데이터가 없습니다.
            </p>
            <p className="text-white/50 text-xs" style={{ fontFamily: "var(--font-body)" }}>
              상단 도로 검색에서 측정 도로를 선택해 주세요.
            </p>
          </div>
        ) : (
          <>
            {/* Horizon selector */}
            <div className="liquid-glass-capsule my-4 animate-slide-up-delay-2 flex-nowrap overflow-x-auto no-scrollbar py-1 px-1.5">
              {["지금", "+30분", "+1시간", "+2시간", "+3시간"].map((h) => {
                const isActive = horizon === h
                return (
                  <button
                    key={h}
                    onClick={() => setHorizon(h)}
                    className={`liquid-glass-pill shrink-0 ${isActive ? "is-active" : ""}`}
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {h}
                  </button>
                )
              })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 animate-slide-up-delay-3">
              {/* Main chart */}
              <div
                className="glass lg:col-span-2 p-5"
                style={{ borderRadius: 20 }}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3
                    className="text-[#1a1a2e]"
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: 15,
                    }}
                  >
                    {activeRoad?.road || "선택 도로"} · 교통량 예측 추이
                  </h3>
                  <div
                    className="flex items-center gap-3 text-xs"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    <div className="flex items-center gap-1.5">
                      <div className="w-5 h-1 rounded bg-[#007aff]" />
                      <span className="text-[#6b6b8a]">현재 실측</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div
                        className="w-5 h-1 rounded bg-[#5e5ce6] opacity-60"
                        style={{
                          borderTop: "2px dashed #5e5ce6",
                          background: "none",
                        }}
                      />
                      <span className="text-[#6b6b8a]">AI 예측</span>
                    </div>
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart
                    data={predictionData}
                    margin={{ left: -20, right: 10 }}
                  >
                    <defs>
                      <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="5%"
                          stopColor="#007aff"
                          stopOpacity={0.15}
                        />
                        <stop
                          offset="95%"
                          stopColor="#007aff"
                          stopOpacity={0}
                        />
                      </linearGradient>
                      <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="5%"
                          stopColor="#5e5ce6"
                          stopOpacity={0.15}
                        />
                        <stop
                          offset="95%"
                          stopColor="#5e5ce6"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(0,0,0,0.06)"
                    />
                    <XAxis
                      dataKey="time"
                      interval={isMobile ? 1 : 0}
                      tick={{
                        fontSize: isMobile ? 9 : 11,
                        fill: "#6b6b8a",
                        fontFamily: "var(--font-mono)",
                      }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{
                        fontSize: 10,
                        fill: "#6b6b8a",
                        fontFamily: "var(--font-mono)",
                      }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "rgba(255,255,255,0.95)",
                        border: "1px solid rgba(0,0,0,0.08)",
                        borderRadius: 12,
                        fontFamily: "var(--font-body)",
                        fontSize: 12,
                      }}
                      formatter={(value, name) => {
                        const speed = Number(value ?? 0)
                        return [
                          speed ? `${speed.toLocaleString()} km/h` : "미정",
                          name === "actual" ? "실제 속도" : "AI 예측 속도",
                        ]
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="actual"
                      stroke="#007aff"
                      strokeWidth={2.5}
                      fill="url(#actualGrad)"
                      dot={{ r: 4, fill: "#007aff" }}
                      activeDot={{ r: 6 }}
                      connectNulls={false}
                    />
                    <Area
                      type="monotone"
                      dataKey="predicted"
                      stroke="#5e5ce6"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      fill="url(#predGrad)"
                      dot={false}
                      activeDot={{ r: 5, fill: "#5e5ce6" }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Confidence + model info */}
              <div className="flex flex-col gap-3">
                <div className="glass p-5" style={{ borderRadius: 20 }}>
                  <h3
                    className="text-[#1a1a2e] mb-4"
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: 15,
                    }}
                  >
                    예측 신뢰도
                  </h3>
                  <div className="flex flex-col gap-3">
                    {predictionData.map((d) => (
                      <div key={d.time}>
                        <div
                          className="flex justify-between text-xs mb-1"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
                          <span className="text-[#4a4a68] font-medium">
                            {d.time}
                          </span>
                          <span
                            className="text-[#6b6b8a]"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {d.confidence}%
                          </span>
                        </div>
                        <div
                          className="h-1.5 rounded-full"
                          style={{ background: "rgba(240,242,248,0.9)" }}
                        >
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${d.confidence}%`,
                              background:
                                d.confidence > 88
                                  ? "#34c759"
                                  : d.confidence > 75
                                    ? "#007aff"
                                    : d.confidence > 65
                                      ? "#ff9500"
                                      : "#ff3b30",
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div
                  className="p-4"
                  style={{
                    borderRadius: 20,
                    background: "rgba(94,92,230,0.06)",
                    border: "1px solid rgba(94,92,230,0.15)",
                  }}
                >
                  <h4
                    className="text-[#5e5ce6] mb-2"
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: 13,
                    }}
                  >
                    AI Prediction Model
                  </h4>
                  {[
                    { label: "알고리즘", value: activeRoad?.algorithm || predState.roads[0]?.algorithm || "Loading..." },
                    {
                      label: "예측 기준",
                      value: new Date().toLocaleTimeString("ko-KR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      }),
                    },
                    { label: "학습 모델", value: activeRoad?.model_version || predState.roads[0]?.model_version || "Loading..." },
                    { label: "Forecast 범위", value: "최대 3시간" },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex justify-between py-1.5 border-b border-[rgba(94,92,230,0.1)] last:border-0"
                    >
                      <span
                        className="text-xs text-[#6b6b8a]"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {item.label}
                      </span>
                      <span
                        className="text-xs font-medium text-[#4a4a68]"
                        style={{ fontFamily: "var(--font-mono)" }}
                      >
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Congestion forecast table */}
            {congestionPrediction.length > 0 && (
              <div
                className="glass p-5 mt-4 animate-slide-up-delay-4"
                style={{ borderRadius: 20 }}
              >
                <h3
                  className="text-[#1a1a2e] mb-4"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: 15,
                  }}
                >
                  {roadQuery.trim()
                    ? `“${roadQuery}” 검색 결과`
                    : "도로별 혼잡 예측"}
                </h3>
                <div className="overflow-x-auto">
                  <table
                    className="w-full text-sm"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    <thead>
                      <tr>
                        {["도로명", "현재", "+30분", "+1시간", "추세"].map(
                          (h) => (
                            <th
                              key={h}
                              className="text-left text-xs text-[#6b6b8a] font-medium pb-3 pr-4"
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {congestionPrediction.map((r) => (
                        <tr
                          key={r.road}
                          className="border-t border-black/[0.04]"
                        >
                          <td className="py-3 pr-4 text-sm font-medium text-[#1a1a2e]">
                            {r.road}
                          </td>
                          {[r.current, r.next30, r.next60].map((level, i) => {
                            const s = levelBg[level as keyof typeof levelBg] || levelBg["원활"]
                            return (
                              <td key={i} className="py-3 pr-4">
                                <span
                                  className="px-2.5 py-1 rounded-lg text-xs font-medium"
                                  style={{ background: s.bg, color: s.text }}
                                >
                                  {level}
                                </span>
                              </td>
                            )
                          })}
                          <td className="py-3">
                            <span
                              className="font-bold text-sm"
                              style={{
                                color:
                                  trendColor[
                                    r.trend as keyof typeof trendColor
                                  ] || "#007aff",
                              }}
                            >
                              {trendIcon[r.trend as keyof typeof trendIcon] || "→"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

import { useState } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts"
import Sidebar from "../components/Sidebar"
import {
  predictionData as defaultPredictionData,
  congestionPrediction as defaultCongestionPrediction,
} from "../data/mock"
import { fetchPredictionData } from "../services/api"
import { useEffect } from "react"

const trendColor = { up: "#ff3b30", down: "#34c759", stable: "#007aff" }
const trendIcon = { up: "↑", down: "↓", stable: "→" }
const levelBg = {
  원활: { bg: "rgba(52,199,89,0.12)", text: "#34c759" },
  서행: { bg: "rgba(255,149,0,0.12)", text: "#ff9500" },
  혼잡: { bg: "rgba(255,59,48,0.12)", text: "#ff3b30" },
}

export default function Prediction() {
  const [horizon, setHorizon] = useState("+1시간")
  const [predState, setPredState] = useState({
    predictions: defaultPredictionData,
    congestion: defaultCongestionPrediction,
    latestAt: null as string | null,
    isFromDb: false,
  })

  useEffect(() => {
    let active = true
    fetchPredictionData().then((res) => {
      if (active) {
        setPredState(res)
      }
    })
    return () => {
      active = false
    }
  }, [])

  const predictionData = predState.predictions
  const congestionPrediction = predState.congestion

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0 px-4 md:px-8 pt-6">
        <div className="flex items-start justify-between mb-1">
          <div>
            <h1
              className="text-[#1a1a2e]"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 26,
                letterSpacing: "-0.02em",
              }}
            >
              AI 예측
            </h1>
            <p
              className="text-[#6b6b8a] text-sm mt-0.5"
              style={{ fontFamily: "var(--font-body)" }}
            >
              머신러닝 기반 미래 교통량 예측 UI · 최대 3시간
            </p>
          </div>
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium"
            style={{
              background: predState.isFromDb ? "rgba(52,199,89,0.1)" : "rgba(94,92,230,0.1)",
              color: predState.isFromDb ? "#248a3d" : "#5e5ce6",
              border: predState.isFromDb
                ? "1px solid rgba(52,199,89,0.2)"
                : "1px solid rgba(94,92,230,0.2)",
              fontFamily: "var(--font-body)",
            }}
          >
            <div
              className={`w-1.5 h-1.5 rounded-full pulse-dot ${
                predState.isFromDb ? "bg-[#34c759]" : "bg-[#5e5ce6]"
              }`}
            />
            {predState.isFromDb ? "DB 학습 모델" : "예시 모델"} · 신뢰도 {predictionData[0].confidence}%
          </div>
        </div>

        {/* Horizon selector */}
        <div className="flex gap-2 my-4">
          {["지금", "+30분", "+1시간", "+2시간", "+3시간"].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className="px-4 py-2 text-sm font-medium transition-all"
              style={{
                borderRadius: 14,
                background:
                  horizon === h
                    ? "linear-gradient(135deg, #5e5ce6, #007aff)"
                    : "rgba(255,255,255,0.72)",
                color: horizon === h ? "white" : "#6b6b8a",
                border: "1px solid rgba(255,255,255,0.8)",
                boxShadow:
                  horizon === h
                    ? "0 4px 16px rgba(94,92,230,0.3)"
                    : "0 2px 8px rgba(0,0,0,0.06)",
                fontFamily: "var(--font-display)",
              }}
            >
              {h}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Main chart */}
          <div className="glass lg:col-span-2 p-5" style={{ borderRadius: 20 }}>
            <div className="flex items-center justify-between mb-4">
              <h3
                className="text-[#1a1a2e]"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: 15,
                }}
              >
                교통량 예측 vs 실제
              </h3>
              <div
                className="flex items-center gap-3 text-xs"
                style={{ fontFamily: "var(--font-body)" }}
              >
                <div className="flex items-center gap-1.5">
                  <div className="w-5 h-1 rounded bg-[#007aff]" />
                  <span className="text-[#6b6b8a]">실제</span>
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
                    <stop offset="5%" stopColor="#007aff" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#007aff" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#5e5ce6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#5e5ce6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(0,0,0,0.06)"
                />
                <XAxis
                  dataKey="time"
                  tick={{
                    fontSize: 11,
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
                    const volume = Number(value ?? 0)
                    return [
                      volume ? `${volume.toLocaleString()}대` : "예측 구간",
                      name === "actual" ? "실제 교통량" : "AI 예측",
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
                { label: "알고리즘", value: "학습 후 연동" },
                {
                  label: "예측 기준",
                  value: new Date().toLocaleTimeString("ko-KR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  }),
                },
                { label: "학습 데이터", value: "수집 후 확정" },
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
        <div className="glass p-5 mt-4" style={{ borderRadius: 20 }}>
          <h3
            className="text-[#1a1a2e] mb-4"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: 15,
            }}
          >
            도로별 혼잡 예측
          </h3>
          <div className="overflow-x-auto">
            <table
              className="w-full text-sm"
              style={{ fontFamily: "var(--font-body)" }}
            >
              <thead>
                <tr>
                  {["도로명", "현재", "+30분", "+1시간", "추세"].map((h) => (
                    <th
                      key={h}
                      className="text-left text-xs text-[#6b6b8a] font-medium pb-3 pr-4"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {congestionPrediction.map((r) => (
                  <tr key={r.road} className="border-t border-black/[0.04]">
                    <td className="py-3 pr-4 text-sm font-medium text-[#1a1a2e]">
                      {r.road}
                    </td>
                    {[r.current, r.next30, r.next60].map((level, i) => {
                      const s = levelBg[(level as keyof typeof levelBg)]
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
                            trendColor[(r.trend as keyof typeof trendColor)],
                        }}
                      >
                        {trendIcon[(r.trend as keyof typeof trendIcon)]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}

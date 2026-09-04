import { useState } from "react"
import { useNavigate } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import MapPlaceholder from "../components/MapPlaceholder"
import { kpiData, incidents } from "../data/mock"

const kpis = [
  {
    label: "서울 평균 속도",
    value: `${kpiData.avgSpeed}`,
    unit: "km/h",
    delta: `${kpiData.avgSpeedDelta}`,
    color: "#ff9500",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M10 6v4l2.5 2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    label: "현재 돌발상황",
    value: `${kpiData.incidents}`,
    unit: "건",
    delta: "+2",
    color: "#ff3b30",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 3L2 17h16L10 3z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path
          d="M10 9v4"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="10" cy="14.5" r="0.75" fill="currentColor" />
      </svg>
    ),
  },
  {
    label: "혼잡 도로 구간",
    value: `${kpiData.congested}`,
    unit: "구간",
    delta: "+3",
    color: "#ff3b30",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M2 10h16M6 6h8M8 14h4"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    label: "AI 예측 혼잡",
    value: `${kpiData.aiPredicted}`,
    unit: "구간",
    delta: "+1시간",
    color: "#5e5ce6",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M6 13l2-4 3 3 3-6"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [search, setSearch] = useState("")

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />

      <main className="flex-1 md:pl-20 pb-24 md:pb-0">
        {/* Header */}
        <div className="px-4 md:px-8 pt-6 pb-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1
                className="text-[#1a1a2e] leading-tight"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: 26,
                  letterSpacing: "-0.02em",
                }}
              >
                교통 대시보드
              </h1>
              <p
                className="text-[#6b6b8a] text-sm mt-0.5"
                style={{ fontFamily: "var(--font-body)" }}
              >
                서울 교통 UI 데모 · 예시 데이터{" "}
                <span className="pulse-dot inline-block w-1.5 h-1.5 bg-[#5e5ce6] rounded-full ml-1" />
              </p>
            </div>
            <div className="text-right hidden sm:block">
              <p
                className="text-xs text-[#6b6b8a]"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {new Date().toLocaleDateString("ko-KR", {
                  month: "short",
                  day: "numeric",
                  weekday: "short",
                })}
              </p>
              <p
                className="text-sm font-semibold text-[#1a1a2e]"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {new Date().toLocaleTimeString("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            {kpis.map((k) => (
              <div
                key={k.label}
                className="glass p-4"
                style={{ borderRadius: 20 }}
              >
                <div className="flex items-start justify-between mb-2">
                  <div
                    className="w-8 h-8 flex items-center justify-center"
                    style={{
                      background: `${k.color}18`,
                      borderRadius: 10,
                      color: k.color,
                    }}
                  >
                    {k.icon}
                  </div>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{
                      background: `${k.color}15`,
                      color: k.color,
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {k.delta}
                  </span>
                </div>
                <div
                  className="text-[#1a1a2e]"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 700,
                    fontSize: 28,
                    letterSpacing: "-0.02em",
                  }}
                >
                  {k.value}
                  <span className="text-sm font-normal text-[#6b6b8a] ml-1">
                    {k.unit}
                  </span>
                </div>
                <p
                  className="text-xs text-[#6b6b8a] mt-0.5"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  {k.label}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Map + Side panel */}
        <div className="px-4 md:px-8 flex flex-col lg:flex-row gap-4">
          {/* Map */}
          <div
            className="glass flex-1"
            style={{ borderRadius: 24, overflow: "hidden" }}
          >
            {/* Search bar */}
            <div className="p-3 border-b border-white/50">
              <div className="relative">
                <svg
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6b6b8a]"
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                >
                  <circle
                    cx="7"
                    cy="7"
                    r="5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  />
                  <path
                    d="M11 11l3 3"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
                <input
                  className="w-full pl-9 pr-4 py-2.5 text-sm outline-none placeholder:text-[#b0b0c8]"
                  style={{
                    background: "rgba(240,242,248,0.8)",
                    borderRadius: 14,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  placeholder="도로명, 지역, 교통 측정지점을 검색하세요"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <MapPlaceholder height={420} />
          </div>

          {/* Right panel */}
          <div className="lg:w-72 flex flex-col gap-3">
            {/* Quick routes */}
            <div className="glass p-4" style={{ borderRadius: 20 }}>
              <h3
                className="text-[#1a1a2e] mb-3"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: 14,
                }}
              >
                자주 이용하는 경로
              </h3>
              {[
                {
                  label: "출근",
                  route: "합정 → 역삼",
                  time: 43,
                  delta: "+8",
                  color: "#ff9500",
                },
                {
                  label: "귀가",
                  route: "역삼 → 합정",
                  time: 52,
                  delta: "+14",
                  color: "#ff3b30",
                },
              ].map((r) => (
                <div
                  key={r.label}
                  className="flex items-center justify-between py-2.5 cursor-pointer hover:bg-white/30 px-2 -mx-2 rounded-xl transition-colors"
                  onClick={() => navigate("/route")}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{
                          background: "rgba(240,242,248,0.9)",
                          color: "#4a4a68",
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        {r.label}
                      </span>
                      <span
                        className="text-xs text-[#6b6b8a]"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {r.route}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span
                        className="font-semibold"
                        style={{
                          fontFamily: "var(--font-display)",
                          fontSize: 18,
                          color: "#1a1a2e",
                          letterSpacing: "-0.01em",
                        }}
                      >
                        {r.time}분
                      </span>
                      <span
                        className="text-xs font-medium"
                        style={{
                          color: r.color,
                          fontFamily: "var(--font-mono)",
                        }}
                      >
                        {r.delta}분
                      </span>
                    </div>
                  </div>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    className="text-[#b0b0c8]"
                  >
                    <path
                      d="M6 4l4 4-4 4"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              ))}
            </div>

            {/* Recent incidents */}
            <div className="glass p-4" style={{ borderRadius: 20 }}>
              <div className="flex items-center justify-between mb-3">
                <h3
                  className="text-[#1a1a2e]"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  최근 돌발상황
                </h3>
                <button
                  onClick={() => navigate("/incidents")}
                  className="text-xs text-[#007aff]"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  전체보기
                </button>
              </div>
              <div className="flex flex-col gap-2">
                {incidents.slice(0, 4).map((inc) => {
                  const colors: Record<string, string> = {
                    high: "#ff3b30",
                    medium: "#ff9500",
                    low: "#34c759",
                  }
                  return (
                    <div key={inc.id} className="flex items-start gap-2.5">
                      <div
                        className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                        style={{ background: colors[inc.impact] }}
                      />
                      <div>
                        <p
                          className="text-xs font-medium text-[#1a1a2e]"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
                          {inc.type} · {inc.road}
                        </p>
                        <p
                          className="text-xs text-[#6b6b8a]"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
                          {inc.startTime} 발생
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* AI forecast teaser */}
            <div
              className="p-4 text-white"
              style={{
                borderRadius: 20,
                background:
                  "linear-gradient(135deg, rgba(94,92,230,0.85), rgba(0,122,255,0.85))",
                backdropFilter: "blur(16px)",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-xl bg-white/20 flex items-center justify-center">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle
                      cx="7"
                      cy="7"
                      r="5.5"
                      stroke="white"
                      strokeWidth="1.5"
                    />
                    <path
                      d="M4 9l2-3 2 2 2-4"
                      stroke="white"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
                <span
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: 13,
                  }}
                >
                  AI 예측
                </span>
              </div>
              <p
                style={{
                  fontSize: 12,
                  opacity: 0.9,
                  fontFamily: "var(--font-body)",
                  lineHeight: 1.5,
                }}
              >
                +1시간 후 강변북로 혼잡 심화 예측. 올림픽대로 우회 권장.
              </p>
              <button
                onClick={() => navigate("/prediction")}
                className="mt-3 text-xs font-semibold bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded-xl transition-colors"
                style={{ fontFamily: "var(--font-body)" }}
              >
                자세히 보기 →
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

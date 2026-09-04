import { useState } from "react"
import Sidebar from "../components/Sidebar"
import MapPlaceholder from "../components/MapPlaceholder"
import { routes } from "../data/mock"

const trafficColor = { green: "#34c759", yellow: "#ff9500", red: "#ff3b30" }
const trafficLabel = { green: "원활", yellow: "서행", red: "혼잡" }

export default function Route() {
  const [origin, setOrigin] = useState("마포구 합정동")
  const [dest, setDest] = useState("강남구 역삼동")
  const [selected, setSelected] = useState("B")

  const selectedRoute = routes.find((r) => r.id === selected)!

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0">
        <div className="px-4 md:px-8 pt-6 pb-4">
          <h1
            className="text-[#1a1a2e] mb-1"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: 26,
              letterSpacing: "-0.02em",
            }}
          >
            경로 분석
          </h1>
          <p
            className="text-[#6b6b8a] text-sm mb-4"
            style={{ fontFamily: "var(--font-body)" }}
          >
            실시간 데이터 + AI 예측을 결합한 최적 경로
          </p>

          {/* Search */}
          <div className="glass p-4 mb-4" style={{ borderRadius: 20 }}>
            <div className="flex flex-col sm:flex-row gap-2 items-center">
              <div className="relative flex-1">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2 border-[#007aff] bg-white" />
                <input
                  className="w-full pl-9 pr-4 py-3 text-sm outline-none"
                  style={{
                    background: "rgba(240,242,248,0.9)",
                    borderRadius: 14,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                />
              </div>
              <button
                onClick={() => {
                  const t = origin
                  setOrigin(dest)
                  setDest(t)
                }}
                className="p-2.5 rounded-xl hover:bg-white/60 transition-colors"
                style={{
                  border: "1px solid rgba(0,122,255,0.2)",
                  color: "#007aff",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M8 2v12M5 11l3 3 3-3M5 5l3-3 3 3"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <div className="relative flex-1">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-sm bg-[#5e5ce6]" />
                <input
                  className="w-full pl-9 pr-4 py-3 text-sm outline-none"
                  style={{
                    background: "rgba(240,242,248,0.9)",
                    borderRadius: 14,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  value={dest}
                  onChange={(e) => setDest(e.target.value)}
                />
              </div>
              <button
                className="px-5 py-3 font-semibold text-white text-sm whitespace-nowrap"
                style={{
                  borderRadius: 14,
                  background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                  fontFamily: "var(--font-display)",
                }}
              >
                AI 분석
              </button>
            </div>
          </div>
        </div>

        <div className="px-4 md:px-8 flex flex-col lg:flex-row gap-4">
          {/* Route list */}
          <div className="lg:w-80 flex flex-col gap-3">
            {routes.map((r) => {
              const isSelected = r.id === selected
              const color = trafficColor[r.trafficLevel]
              return (
                <div
                  key={r.id}
                  onClick={() => setSelected(r.id)}
                  className="glass cursor-pointer transition-all hover:scale-[1.01]"
                  style={{
                    borderRadius: 20,
                    border: isSelected
                      ? "1.5px solid rgba(0,122,255,0.4)"
                      : undefined,
                    boxShadow: isSelected
                      ? "0 0 0 3px rgba(0,122,255,0.1), 0 8px 32px rgba(0,0,0,0.08)"
                      : undefined,
                  }}
                >
                  <div className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-7 h-7 flex items-center justify-center text-sm font-bold"
                          style={{
                            borderRadius: 10,
                            background: isSelected
                              ? "linear-gradient(135deg, #007aff, #5e5ce6)"
                              : "rgba(240,242,248,0.9)",
                            color: isSelected ? "white" : "#4a4a68",
                            fontFamily: "var(--font-display)",
                          }}
                        >
                          {r.id}
                        </div>
                        <div>
                          <p
                            className="font-semibold text-[#1a1a2e]"
                            style={{
                              fontFamily: "var(--font-display)",
                              fontSize: 15,
                            }}
                          >
                            {r.label}
                          </p>
                          <p
                            className="text-xs text-[#6b6b8a]"
                            style={{ fontFamily: "var(--font-body)" }}
                          >
                            via {r.via}
                          </p>
                        </div>
                      </div>
                      {r.ai && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-semibold text-white"
                          style={{
                            background:
                              "linear-gradient(135deg, #5e5ce6, #007aff)",
                            fontFamily: "var(--font-body)",
                          }}
                        >
                          AI 추천
                        </span>
                      )}
                    </div>

                    <div className="flex items-end gap-3">
                      <div>
                        <span
                          className="text-[#1a1a2e]"
                          style={{
                            fontFamily: "var(--font-display)",
                            fontWeight: 700,
                            fontSize: 28,
                            letterSpacing: "-0.02em",
                          }}
                        >
                          {r.time}
                        </span>
                        <span className="text-sm text-[#6b6b8a] ml-1">분</span>
                      </div>
                      <div
                        className="text-sm text-[#6b6b8a]"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {r.distance}km
                      </div>
                      <div
                        className="ml-auto text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{
                          background: `${color}15`,
                          color,
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        {trafficLabel[r.trafficLevel]}
                      </div>
                    </div>

                    {r.ai && r.reason && (
                      <div
                        className="mt-3 p-3 rounded-xl text-xs leading-relaxed"
                        style={{
                          background: "rgba(94,92,230,0.08)",
                          color: "#4a4a68",
                          border: "1px solid rgba(94,92,230,0.15)",
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        ✦ {r.reason}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Map + detail */}
          <div className="flex-1 flex flex-col gap-3">
            <div
              className="glass"
              style={{ borderRadius: 24, overflow: "hidden" }}
            >
              <MapPlaceholder height={300} />
            </div>

            {/* Route detail */}
            <div className="glass p-5" style={{ borderRadius: 20 }}>
              <h3
                className="text-[#1a1a2e] mb-4"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: 16,
                }}
              >
                {selectedRoute.label} 상세 정보
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  {
                    label: "예상 소요",
                    value: `${selectedRoute.time}분`,
                    color: "#007aff",
                  },
                  {
                    label: "거리",
                    value: `${selectedRoute.distance}km`,
                    color: "#4a4a68",
                  },
                  {
                    label: "평균 속도",
                    value: `${selectedRoute.avgSpeed}km/h`,
                    color: "#4a4a68",
                  },
                  {
                    label: "예상 지연",
                    value:
                      selectedRoute.delay > 0
                        ? `+${selectedRoute.delay}분`
                        : "없음",
                    color: selectedRoute.delay > 0 ? "#ff9500" : "#34c759",
                  },
                  {
                    label: "교통 상황",
                    value: trafficLabel[selectedRoute.trafficLevel],
                    color: trafficColor[selectedRoute.trafficLevel],
                  },
                  {
                    label: "돌발상황",
                    value:
                      selectedRoute.incidents > 0
                        ? `${selectedRoute.incidents}건`
                        : "없음",
                    color: selectedRoute.incidents > 0 ? "#ff3b30" : "#34c759",
                  },
                  {
                    label: "날씨",
                    value: selectedRoute.weather,
                    color: "#007aff",
                  },
                  {
                    label: "AI 추천",
                    value: selectedRoute.ai ? "✓ 해당" : "비해당",
                    color: selectedRoute.ai ? "#5e5ce6" : "#b0b0c8",
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="p-3"
                    style={{
                      background: "rgba(240,242,248,0.6)",
                      borderRadius: 14,
                    }}
                  >
                    <p
                      className="text-xs text-[#6b6b8a] mb-1"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {item.label}
                    </p>
                    <p
                      className="font-semibold"
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: 15,
                        color: item.color,
                      }}
                    >
                      {item.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

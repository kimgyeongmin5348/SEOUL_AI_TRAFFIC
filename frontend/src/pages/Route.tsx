import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import MapPlaceholder from "../components/MapPlaceholder"
import { routes as defaultRoutes } from "../data/mock"
import { getLiveSeoulRoutes, RouteResult } from "../services/routing"
import { fetchFavoriteRoutes, recordRouteSearch, FavoriteRouteItem } from "../services/api"

const trafficColor = { green: "#34c759", yellow: "#ff9500", red: "#ff3b30" }
const trafficLabel = { green: "원활", yellow: "서행", red: "혼잡" }

const POPULAR_ROUTES = [
  { from: "마포구 합정동", to: "강남구 역삼동", label: "합정 ➔ 역삼" },
  { from: "영등포구 여의도동", to: "종로구 광화문", label: "여의도 ➔ 광화문" },
  { from: "송파구 잠실동", to: "마포구 홍대입구", label: "잠실 ➔ 홍대" },
  { from: "구로구 신도림동", to: "강남구 테헤란로", label: "신도림 ➔ 강남" },
  { from: "노원구 상계동", to: "서초구 양재동", label: "노원 ➔ 양재" },
]

export default function Route() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialOrigin = searchParams.get("origin") || "마포구 합정동"
  const initialDest = searchParams.get("dest") || "강남구 역삼동"

  const [origin, setOrigin] = useState(initialOrigin)
  const [dest, setDest] = useState(initialDest)
  const [selected, setSelected] = useState("A")
  const [routeList, setRouteList] = useState<RouteResult[]>(defaultRoutes as unknown as RouteResult[])
  const [originPoint, setOriginPoint] = useState<{ name: string; lat: number; lng: number } | null>(null)
  const [destPoint, setDestPoint] = useState<{ name: string; lat: number; lng: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [dbFavorites, setDbFavorites] = useState<FavoriteRouteItem[]>([])

  useEffect(() => {
    fetchFavoriteRoutes().then((res) => {
      if (res.routes && res.routes.length > 0) {
        setDbFavorites(res.routes)
      }
    })
  }, [])

  const runAnalysis = async (startAddr: string, endAddr: string) => {
    if (!startAddr.trim() || !endAddr.trim()) return
    setLoading(true)
    // DB 경로 검색 횟수 증가 (자동 즐겨찾기 집계)
    recordRouteSearch(startAddr.trim(), endAddr.trim())
    try {
      const res = await getLiveSeoulRoutes(startAddr, endAddr)
      setRouteList(res.routes)
      setOriginPoint(res.origin)
      setDestPoint(res.dest)
      const best = res.routes.find((r) => r.ai) || res.routes[0]
      if (best) {
        setSelected(best.id)
      }
    } catch (err) {
      console.warn("Failed to calculate live routes:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const qOrigin = searchParams.get("origin")
    const qDest = searchParams.get("dest")
    if (qOrigin && qDest) {
      setOrigin(qOrigin)
      setDest(qDest)
      runAnalysis(qOrigin, qDest)
    } else {
      runAnalysis(origin, dest)
    }
  }, [searchParams])

  const selectedRoute = routeList.find((r) => r.id === selected) || routeList[0]

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0">
        <div className="px-4 md:px-8 pt-6 pb-4">
          <div className="flex items-center justify-between mb-1">
            <h1
              className="text-[#1a1a2e]"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 26,
                letterSpacing: "-0.02em",
              }}
            >
              서울 전역 도로망 경로 분석
            </h1>
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{
                background: "rgba(0,122,255,0.1)",
                color: "#007aff",
                fontFamily: "var(--font-body)",
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#007aff] pulse-dot" />
              서울 실시간 주행 궤적 연동
            </span>
          </div>
          <p
            className="text-[#6b6b8a] text-sm mb-4"
            style={{ fontFamily: "var(--font-body)" }}
          >
            실제 서울 도로망 기반 최적 경로 · 실시간 교통 상황 및 우회로 반영
          </p>

          {/* Search Box */}
          <div className="glass p-4 mb-4" style={{ borderRadius: 20 }}>
            <div className="flex flex-col sm:flex-row gap-2 items-center">
              <div className="relative flex-1 w-full">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border-2 border-[#007aff] bg-white" />
                <input
                  className="w-full pl-9 pr-4 py-3 text-sm outline-none placeholder:text-[#b0b0c8]"
                  style={{
                    background: "rgba(240,242,248,0.9)",
                    borderRadius: 14,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  placeholder="출발지 (예: 마포구 합정동, 영등포, 노원)"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setSearchParams({ origin, dest })
                      runAnalysis(origin, dest)
                    }
                  }}
                />
              </div>

              <button
                onClick={() => {
                  const t = origin
                  setOrigin(dest)
                  setDest(t)
                  setSearchParams({ origin: dest, dest: t })
                  runAnalysis(dest, t)
                }}
                className="p-3 rounded-xl hover:bg-white/70 transition-all border border-black/5 text-[#007aff] cursor-pointer shadow-sm"
                title="출발지/도착지 맞바꾸기"
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

              <div className="relative flex-1 w-full">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-sm bg-[#5e5ce6]" />
                <input
                  className="w-full pl-9 pr-4 py-3 text-sm outline-none placeholder:text-[#b0b0c8]"
                  style={{
                    background: "rgba(240,242,248,0.9)",
                    borderRadius: 14,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  placeholder="도착지 (예: 강남구 역삼동, 광화문, 잠실)"
                  value={dest}
                  onChange={(e) => setDest(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setSearchParams({ origin, dest })
                      runAnalysis(origin, dest)
                    }
                  }}
                />
              </div>

              <button
                onClick={() => {
                  setSearchParams({ origin, dest })
                  runAnalysis(origin, dest)
                }}
                disabled={loading}
                className="w-full sm:w-auto px-6 py-3 font-semibold text-white text-sm whitespace-nowrap cursor-pointer hover:opacity-90 transition-opacity shadow-md disabled:opacity-50"
                style={{
                  borderRadius: 14,
                  background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                  fontFamily: "var(--font-display)",
                }}
              >
                {loading ? "경로 계산 중…" : "AI 경로 분석"}
              </button>
            </div>

            {/* 빠른 추천 경로 칩 */}
            <div className="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-black/5 overflow-x-auto text-xs">
              <span className="text-[#6b6b8a] whitespace-nowrap text-[11px] font-medium">
                {dbFavorites.length > 0 ? "🔥 최다 검색 경로:" : "서울 추천 구간:"}
              </span>
              {(dbFavorites.length > 0
                ? dbFavorites.map((p) => ({
                    from: p.origin,
                    to: p.destination,
                    label: `${p.label} (${p.search_count}회)`,
                  }))
                : POPULAR_ROUTES
              ).map((p) => (
                <button
                  key={p.label}
                  onClick={() => {
                    setOrigin(p.from)
                    setDest(p.to)
                    setSearchParams({ origin: p.from, dest: p.to })
                    runAnalysis(p.from, p.to)
                  }}
                  className="px-2.5 py-1 rounded-lg bg-white/70 hover:bg-white text-[#33334d] border border-black/5 transition-all text-[11px] whitespace-nowrap cursor-pointer font-medium shadow-2xs"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="px-4 md:px-8 flex flex-col lg:flex-row gap-4">
          {/* Route list */}
          <div className="lg:w-84 flex flex-col gap-3">
            {routeList.map((r) => {
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
                      ? "2px solid rgba(0,122,255,0.6)"
                      : "1px solid rgba(255,255,255,0.7)",
                    boxShadow: isSelected
                      ? "0 0 0 3px rgba(0,122,255,0.15), 0 8px 32px rgba(0,0,0,0.08)"
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
                            경유: {r.via}
                          </p>
                        </div>
                      </div>
                      {r.ai && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-semibold text-white shadow-xs"
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

                    <div className="flex items-end gap-3 mt-3">
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
                        className="text-sm text-[#6b6b8a] pb-1"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {r.distance}km
                      </div>
                      <div
                        className="ml-auto text-xs px-2.5 py-1 rounded-full font-semibold"
                        style={{
                          background: `${color}18`,
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
                          color: "#3f3f58",
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
              <MapPlaceholder
                height={460}
                routeCoordinates={selectedRoute?.coordinates}
                originPoint={originPoint || undefined}
                destPoint={destPoint || undefined}
              />
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
                {selectedRoute?.label} 주행 상세 분석
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  {
                    label: "예상 소요 시간",
                    value: `${selectedRoute?.time}분`,
                    color: "#007aff",
                  },
                  {
                    label: "실제 주행 거리",
                    value: `${selectedRoute?.distance}km`,
                    color: "#4a4a68",
                  },
                  {
                    label: "구간 평균 속도",
                    value: `${selectedRoute?.avgSpeed}km/h`,
                    color: "#4a4a68",
                  },
                  {
                    label: "정체 지연 시간",
                    value:
                      selectedRoute?.delay > 0
                        ? `+${selectedRoute.delay}분`
                        : "지연 없음",
                    color: selectedRoute?.delay > 0 ? "#ff9500" : "#34c759",
                  },
                  {
                    label: "실시간 교통 흐름",
                    value: trafficLabel[selectedRoute?.trafficLevel || "green"],
                    color: trafficColor[selectedRoute?.trafficLevel || "green"],
                  },
                  {
                    label: "구간 돌발상황",
                    value:
                      selectedRoute?.incidents > 0
                        ? `${selectedRoute.incidents}건 발생`
                        : "돌발 없음",
                    color: selectedRoute?.incidents > 0 ? "#ff3b30" : "#34c759",
                  },
                  {
                    label: "도로 날씨",
                    value: selectedRoute?.weather || "맑음",
                    color: "#007aff",
                  },
                  {
                    label: "AI 최적 추천 여부",
                    value: selectedRoute?.ai ? "★ 추천 경로" : "일반 경로",
                    color: selectedRoute?.ai ? "#5e5ce6" : "#6b6b8a",
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

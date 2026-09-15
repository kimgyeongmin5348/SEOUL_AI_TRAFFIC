import { useState, useEffect, useCallback } from "react"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import MapPlaceholder, { type IncidentItem } from "../components/MapPlaceholder"
import { fetchIncidentsData } from "../services/api"

const impactColor = { high: "#ff3b30", medium: "#ff9500", low: "#34c759" }
const impactLabel = { high: "높음", medium: "보통", low: "낮음" }
const typeIcon: Record<string, string> = {
  사고: "🚨",
  공사: "🚧",
  차량고장: "🚗",
  도로통제: "🚫",
  낙하물: "⚠️",
}

export default function Incidents() {
  const [selected, setSelected] = useState<number | string | null>(null)
  const [filter, setFilter] = useState("전체")
  const [loading, setLoading] = useState(true)

  const handleSelectIncident = useCallback((inc: IncidentItem) => {
    setSelected((prev) => (prev === inc.id ? null : inc.id))
  }, [])
  const [incidentsState, setIncidentsState] = useState<{
    incidents: Array<{
      id: number | string
      type: string
      road: string
      location: string
      startTime: string
      estEnd: string
      description: string
      impact: "high" | "medium" | "low"
      severity: number
      tmX: number | null
      tmY: number | null
    }>
    latestAt: string | null
    isFromDb: boolean
  }>({
    incidents: [],
    latestAt: null,
    isFromDb: false,
  })

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchIncidentsData()
      .then((res) => {
        if (active) {
          setIncidentsState(res)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const incidents = incidentsState.incidents

  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 640 : false
  )

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 640)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])
  const filters = ["전체", "사고", "공사", "통제", "기타"]

  const filtered =
    filter === "전체"
      ? incidents
      : incidents.filter((i) =>
          filter === "사고"
            ? i.type === "사고"
            : filter === "공사"
              ? i.type === "공사"
              : filter === "통제"
                ? i.type === "도로통제"
                : filter === "기타"
                  ? !["사고", "공사", "도로통제"].includes(i.type)
                  : true,
        )

  const selInc = incidents.find(
    (i) => selected != null && String(i.id) === String(selected)
  )

  return (
    <div className="min-h-full flex relative" style={{ minHeight: "100vh" }}>
      <SubpageBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 md:pl-28 md:pr-8 px-4 pb-24 md:pb-8 pt-[max(68px,calc(env(safe-area-inset-top)+60px))] md:pt-6 max-w-7xl mx-auto w-full">
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-1">
            <h1
              className="text-white"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 26,
                letterSpacing: "-0.02em",
                textShadow: "0 2px 12px rgba(0,0,0,0.35)",
              }}
            >
              돌발상황
            </h1>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#ff3b30] inline-block shadow-[0_0_8px_rgba(255,59,48,0.7)]" />
              <span
                className="text-sm font-medium text-[#ff6961]"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {incidents.length}건 발생 중
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 mb-5">
            <p
              className="text-white/70 text-sm"
              style={{ fontFamily: "var(--font-body)" }}
            >
              사고 · 공사 · 차량고장 · 도로통제 실시간 현황
            </p>
            {incidentsState.isFromDb && (
              <span
                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium"
                style={{
                  background: "rgba(52,199,89,0.2)",
                  color: "#34c759",
                  border: "1px solid rgba(52,199,89,0.3)",
                  fontFamily: "var(--font-body)",
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#34c759] animate-pulse" />
                DB 실시간 연동
              </span>
            )}
            {incidentsState.latestAt && (
              <span
                className="text-xs text-white/70"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                수집:{" "}
                {new Date(incidentsState.latestAt).toLocaleTimeString("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
        </div>

        {loading ? (
          <div
            className="glass p-12 text-center flex flex-col items-center justify-center gap-3 my-8 animate-pulse"
            style={{ borderRadius: 20 }}
          >
            <div className="w-8 h-8 rounded-full border-2 border-[#ff3b30] border-t-transparent animate-spin" />
            <p
              className="text-white/80 text-sm font-medium"
              style={{ fontFamily: "var(--font-body)" }}
            >
              실시간 DB 돌발상황 데이터를 수신 중입니다...
            </p>
          </div>
        ) : (
          <div className="flex flex-col lg:flex-row gap-4">
            {/* List */}
            <div className="lg:w-[400px] flex flex-col gap-3 animate-slide-up-delay-1">
              {/* Filters */}
              <div className="liquid-glass-capsule w-full justify-between p-1 overflow-x-auto no-scrollbar">
                {filters.map((f) => {
                  const isActive = filter === f
                  return (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={`liquid-glass-pill flex-1 shrink-0 text-center py-1.5 px-2 text-xs ${
                        isActive ? "is-active" : ""
                      }`}
                    >
                      {f}
                    </button>
                  )
                })}
              </div>

              <div
                className="flex flex-col gap-2 overflow-y-auto no-scrollbar"
                style={{ maxHeight: isMobile ? 360 : 540 }}
              >
                {filtered.length === 0 ? (
                  <div className="glass p-8 text-center" style={{ borderRadius: 18 }}>
                    <p className="text-white/80 text-sm font-medium">
                      현재 등록된 돌발 상황이 없습니다.
                    </p>
                    <p className="text-white/50 text-xs mt-1">
                      서울 시내 도로가 원활합니다.
                    </p>
                  </div>
                ) : (
                  filtered.map((inc) => {
                    const color = impactColor[inc.impact]
                    const isSelected =
                      selected != null && String(inc.id) === String(selected)
                    return (
                      <div
                        key={inc.id}
                        onClick={() => setSelected(isSelected ? null : inc.id)}
                        className="glass item-glide cursor-pointer"
                        style={{
                          borderRadius: 18,
                          border: isSelected ? `1.5px solid ${color}60` : undefined,
                        }}
                      >
                        <div className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2.5">
                              <span className="text-xl">
                                {typeIcon[inc.type] || "⚠️"}
                              </span>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span
                                    className="font-semibold text-[#1a1a2e]"
                                    style={{
                                      fontFamily: "var(--font-display)",
                                      fontSize: 14,
                                    }}
                                  >
                                    {inc.type}
                                  </span>
                                  <span
                                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                                    style={{
                                      background: `${color}18`,
                                      color,
                                      fontFamily: "var(--font-body)",
                                    }}
                                  >
                                    영향 {impactLabel[inc.impact]}
                                  </span>
                                </div>
                                <p
                                  className="text-xs text-[#6b6b8a] mt-0.5"
                                  style={{ fontFamily: "var(--font-body)" }}
                                >
                                  {inc.road}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p
                                className="text-xs text-[#6b6b8a]"
                                style={{ fontFamily: "var(--font-mono)" }}
                              >
                                {inc.startTime}
                              </p>
                              <p
                                className="text-xs text-[#b0b0c8]"
                                style={{ fontFamily: "var(--font-mono)" }}
                              >
                                ~{inc.estEnd}
                              </p>
                            </div>
                          </div>

                          {isSelected && (
                            <div
                              className="mt-3 p-3 rounded-xl text-sm leading-relaxed fade-in"
                              style={{
                                background: "rgba(240,242,248,0.8)",
                                color: "#4a4a68",
                                fontFamily: "var(--font-body)",
                              }}
                            >
                              <p className="text-xs font-medium text-[#1a1a2e] mb-1">
                                📍 {inc.location}
                              </p>
                              <p className="text-xs">{inc.description}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            {/* Map */}
            <div
              className="relative flex-1 min-w-0 glass animate-slide-up-delay-2 flex flex-col"
              style={{ borderRadius: 24, overflow: "hidden" }}
            >
              <MapPlaceholder
                height={isMobile ? 320 : 560}
                incidents={incidents}
                selectedIncidentId={selected}
                onSelectIncident={handleSelectIncident}
                enableTraffic={false}
                enableParking={false}
              />
              {selInc && (
                <div
                  className="absolute bottom-6 right-6 glass p-4 w-64 fade-in"
                  style={{ borderRadius: 18, position: "absolute" }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{typeIcon[selInc.type]}</span>
                    <span
                      className="font-semibold text-[#1a1a2e]"
                      style={{ fontFamily: "var(--font-display)", fontSize: 14 }}
                    >
                      {selInc.type}
                    </span>
                  </div>
                  <p
                    className="text-xs text-[#6b6b8a]"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    {selInc.road} · {selInc.location}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

import { useState } from "react"
import Sidebar from "../components/Sidebar"
import MapPlaceholder from "../components/MapPlaceholder"
import { incidents as defaultIncidents } from "../data/mock"
import { fetchIncidentsData } from "../services/api"
import { useEffect } from "react"

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
  const [selected, setSelected] = useState<number | null>(null)
  const [filter, setFilter] = useState("전체")
  const [incidentsState, setIncidentsState] = useState({
    incidents: defaultIncidents,
    latestAt: null as string | null,
    isFromDb: false,
  })

  useEffect(() => {
    let active = true
    fetchIncidentsData().then((res) => {
      if (active) {
        setIncidentsState(res)
      }
    })
    return () => {
      active = false
    }
  }, [])

  const incidents = incidentsState.incidents
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

  const selInc = incidents.find((i) => i.id === selected)

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0 px-4 md:px-8 pt-6">
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
            돌발상황
          </h1>
          <div className="flex items-center gap-2">
            <span className="pulse-dot w-2 h-2 rounded-full bg-[#ff3b30] inline-block" />
            <span
              className="text-sm font-medium text-[#ff3b30]"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {incidents.length}건 발생 중
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 mb-5">
          <p
            className="text-[#6b6b8a] text-sm"
            style={{ fontFamily: "var(--font-body)" }}
          >
            사고 · 공사 · 차량고장 · 도로통제 실시간 현황
          </p>
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
            style={{
              background: incidentsState.isFromDb
                ? "rgba(52,199,89,0.12)"
                : "rgba(94,92,230,0.12)",
              color: incidentsState.isFromDb ? "#248a3d" : "#5e5ce6",
              fontFamily: "var(--font-body)",
            }}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                incidentsState.isFromDb ? "bg-[#34c759]" : "bg-[#5e5ce6]"
              }`}
            />
            {incidentsState.isFromDb ? "DB 실시간 연동" : "예시 데이터"}
          </span>
          {incidentsState.latestAt && (
            <span
              className="text-xs text-[#6b6b8a]"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              수집: {new Date(incidentsState.latestAt).toLocaleTimeString("ko-KR", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>

        <div className="flex flex-col lg:flex-row gap-4">
          {/* List */}
          <div className="lg:w-[400px] flex flex-col gap-3">
            {/* Filters */}
            <div
              className="glass flex gap-1 p-1.5"
              style={{ borderRadius: 16 }}
            >
              {filters.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className="flex-1 py-1.5 text-xs font-medium transition-all"
                  style={{
                    borderRadius: 11,
                    background:
                      filter === f ? "rgba(0,122,255,0.12)" : "transparent",
                    color: filter === f ? "#007aff" : "#6b6b8a",
                    fontFamily: "var(--font-body)",
                  }}
                >
                  {f}
                </button>
              ))}
            </div>

            <div
              className="flex flex-col gap-2 overflow-y-auto"
              style={{ maxHeight: 540 }}
            >
              {filtered.map((inc) => {
                const color = impactColor[inc.impact]
                const isSelected = inc.id === selected
                return (
                  <div
                    key={inc.id}
                    onClick={() => setSelected(isSelected ? null : inc.id)}
                    className="glass cursor-pointer transition-all hover:scale-[1.01]"
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
              })}
            </div>
          </div>

          {/* Map */}
          <div
            className="relative flex-1 min-w-0 glass flex flex-col"
            style={{ borderRadius: 24, overflow: "hidden" }}
          >
            <MapPlaceholder height={560} incidents={incidents} selectedIncidentId={selected} onSelectIncident={(inc) => setSelected(Number(inc.id))} />
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
      </main>
    </div>
  )
}

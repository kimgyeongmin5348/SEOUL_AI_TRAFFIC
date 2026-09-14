import { useState, useEffect } from "react"
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import { fetchTrafficData, TrafficPeriod, TrafficAnalysisResult } from "../services/api"

const levelColor = { red: "#ff3b30", yellow: "#ff9500", green: "#34c759" }

const PERIOD_OPTIONS: Array<{ key: TrafficPeriod; label: string }> = [
  { key: "today", label: "오늘" },
  { key: "yesterday", label: "어제" },
  { key: "week", label: "1주일" },
  { key: "month", label: "1개월" },
]

export default function Traffic() {
  const [loading, setLoading] = useState(true)
  const [selectedPeriod, setSelectedPeriod] = useState<TrafficPeriod>("today")
  const [selectedRoad, setSelectedRoad] = useState("")
  const [trafficData, setTrafficData] = useState<TrafficAnalysisResult>({
    timeData: [],
    roadSpeeds: [],
    latestAt: null,
    isFromDb: false,
    period: "today",
  })

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchTrafficData(selectedPeriod)
      .then((res) => {
        if (active) {
          setTrafficData(res)
          if (res.roadSpeeds.length > 0) {
            setSelectedRoad((prev) =>
              prev && res.roadSpeeds.some((r) => r.road === prev)
                ? prev
                : res.roadSpeeds[0].road
            )
          }
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [selectedPeriod])

  const roadSpeedData = trafficData.roadSpeeds
  const trafficTimeData = trafficData.timeData
  const road =
    roadSpeedData.find((r) => r.road === selectedRoad) ||
    roadSpeedData[0] ||
    null

  return (
    <div className="min-h-full flex relative" style={{ minHeight: "100vh" }}>
      <SubpageBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 md:pl-28 md:pr-8 px-4 pb-24 md:pb-8 pt-[max(68px,calc(env(safe-area-inset-top)+60px))] md:pt-6 max-w-7xl mx-auto w-full">
        <div className="animate-slide-up">
          <h1
            className="text-white mb-1"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: 26,
              letterSpacing: "-0.02em",
              textShadow: "0 2px 12px rgba(0,0,0,0.35)",
            }}
          >
            교통 분석
          </h1>
          <div className="flex items-center gap-2 mb-5">
            <p
              className="text-white/70 text-sm"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {selectedPeriod === "today"
                ? "오늘 시간대별 교통량 및 실시간 도로 속도"
                : selectedPeriod === "yesterday"
                ? "어제 시간대별 교통량 및 주요 도로 속도"
                : selectedPeriod === "week"
                ? "최근 7일간 일별 교통량 추이 및 주요 도로 속도"
                : "최근 30일간 일별 교통량 추이 및 주요 도로 속도"}
            </p>
            {trafficData.isFromDb && (
              <span
                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium"
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
            {trafficData.latestAt && (
              <span
                className="text-xs text-white/70"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                기준:{" "}
                {new Date(trafficData.latestAt).toLocaleDateString("ko-KR", {
                  month: "numeric",
                  day: "numeric",
                })}{" "}
                {new Date(trafficData.latestAt).toLocaleTimeString("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
        </div>

        {/* Filters */}
        <div
          className="glass animate-slide-up-delay-1 flex flex-wrap gap-2 p-3 mb-5 items-center"
          style={{ borderRadius: 18 }}
        >
          {PERIOD_OPTIONS.map((t) => {
            const isActive = selectedPeriod === t.key
            return (
              <button
                key={t.key}
                onClick={() => setSelectedPeriod(t.key)}
                className="px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all duration-200 cursor-pointer"
                style={{
                  background: isActive
                    ? "rgba(0,122,255,0.18)"
                    : "rgba(0,0,0,0.04)",
                  color: isActive ? "#007aff" : "#6b6b8a",
                  border: isActive
                    ? "1px solid rgba(0,122,255,0.3)"
                    : "1px solid rgba(0,0,0,0.06)",
                  boxShadow: isActive
                    ? "0 2px 8px rgba(0,122,255,0.18)"
                    : "none",
                  fontFamily: "var(--font-body)",
                }}
              >
                {t.label}
              </button>
            )
          })}
          {roadSpeedData.length > 0 && <div className="w-px h-5 bg-black/10 mx-1" />}
          {roadSpeedData.slice(0, 8).map((r) => {
            const isSelected = selectedRoad === r.road
            return (
              <button
                key={r.road}
                onClick={() => setSelectedRoad(r.road)}
                className="px-3 py-1.5 text-xs font-medium rounded-xl transition-all duration-200 cursor-pointer"
                style={{
                  background: isSelected
                    ? "rgba(0,122,255,0.15)"
                    : "transparent",
                  color: isSelected ? "#007aff" : "#6b6b8a",
                  border: isSelected
                    ? "1px solid rgba(0,122,255,0.25)"
                    : "1px solid transparent",
                  fontFamily: "var(--font-body)",
                }}
              >
                {r.road}
              </button>
            )
          })}
        </div>

        {loading ? (
          <div
            className="glass p-12 text-center flex flex-col items-center justify-center gap-3 my-8 animate-pulse"
            style={{ borderRadius: 20 }}
          >
            <div className="w-8 h-8 rounded-full border-2 border-[#007aff] border-t-transparent animate-spin" />
            <p
              className="text-white/80 text-sm font-medium"
              style={{ fontFamily: "var(--font-body)" }}
            >
              실시간 DB 교통 데이터를 수신 중입니다...
            </p>
          </div>
        ) : roadSpeedData.length === 0 && trafficTimeData.length === 0 ? (
          <div
            className="glass p-12 text-center my-8"
            style={{ borderRadius: 20 }}
          >
            <p
              className="text-white/80 text-base font-semibold mb-1"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DB에 저장된 교통 데이터가 없습니다.
            </p>
            <p
              className="text-white/50 text-xs"
              style={{ fontFamily: "var(--font-body)" }}
            >
              수집 서비스가 동작 중인지 확인해 주세요.
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4 animate-slide-up-delay-2">
              {/* Volume chart */}
              <div
                className="glass lg:col-span-2 p-5"
                style={{ borderRadius: 20 }}
              >
                <h3
                  className="text-[#1a1a2e] mb-4 flex items-center justify-between"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: 15,
                  }}
                >
                  <span>
                    {selectedPeriod === "today"
                      ? "오늘 시간대별 교통량"
                      : selectedPeriod === "yesterday"
                      ? "어제 시간대별 교통량"
                      : selectedPeriod === "week"
                      ? "최근 7일간 일별 교통량 추이"
                      : "최근 30일간 일별 교통량 추이"}
                  </span>
                  <span
                    className="text-xs text-[#6b6b8a] font-normal"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {selectedPeriod === "today" || selectedPeriod === "yesterday"
                      ? "단위: 대/시간"
                      : "단위: 대/일"}
                  </span>
                </h3>
                {trafficTimeData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart
                      data={trafficTimeData}
                      margin={{ left: -20, right: 10 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(0,0,0,0.06)"
                      />
                      <XAxis
                        dataKey="time"
                        tick={{
                          fontSize: 10,
                          fill: "#6b6b8a",
                          fontFamily: "var(--font-mono)",
                        }}
                        tickLine={false}
                        axisLine={false}
                        interval={
                          selectedPeriod === "week"
                            ? 0
                            : selectedPeriod === "month"
                            ? 3
                            : 1
                        }
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
                        formatter={(value) => [
                          `${Number(value ?? 0).toLocaleString()}대`,
                          "교통량",
                        ]}
                      />
                      {(selectedPeriod === "today" || selectedPeriod === "yesterday") &&
                        trafficTimeData.some((d) => d.time === "08:00") && (
                          <ReferenceLine
                            x="08:00"
                            stroke="#ff3b30"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{
                              value: "출근 피크",
                              position: "top",
                              fontSize: 9,
                              fill: "#ff3b30",
                              fontFamily: "var(--font-mono)",
                            }}
                          />
                        )}
                      {(selectedPeriod === "today" || selectedPeriod === "yesterday") &&
                        trafficTimeData.some((d) => d.time === "18:00") && (
                          <ReferenceLine
                            x="18:00"
                            stroke="#ff9500"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{
                              value: "퇴근 피크",
                              position: "top",
                              fontSize: 9,
                              fill: "#ff9500",
                              fontFamily: "var(--font-mono)",
                            }}
                          />
                        )}
                      <Line
                        type="monotone"
                        dataKey="volume"
                        stroke="#007aff"
                        strokeWidth={2.5}
                        dot={selectedPeriod === "week" ? { r: 3, fill: "#007aff" } : false}
                        activeDot={{ r: 5, fill: "#007aff" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[220px] flex items-center justify-center text-xs text-[#6b6b8a]">
                    선택한 기간의 교통량 데이터가 없습니다.
                  </div>
                )}
              </div>

              {/* Road detail */}
              <div className="glass p-5" style={{ borderRadius: 20 }}>
                <h3
                  className="text-[#1a1a2e] mb-4"
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 600,
                    fontSize: 15,
                  }}
                >
                  {road?.road || "선택된 도로 없음"}
                </h3>
                {road ? (
                  <div className="flex flex-col gap-3">
                    {[
                      {
                        label: "현재 속도",
                        value: `${road.speed} km/h`,
                        color:
                          levelColor[
                            (road.level as keyof typeof levelColor) || "yellow"
                          ],
                      },
                      {
                        label: "평균 속도",
                        value: `${road.avg} km/h`,
                        color: "#4a4a68",
                      },
                      {
                        label: "혼잡 상태",
                        value:
                          road.level === "red"
                            ? "혼잡"
                            : road.level === "yellow"
                              ? "서행"
                              : "원활",
                        color:
                          levelColor[
                            (road.level as keyof typeof levelColor) || "yellow"
                          ],
                      },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between p-3"
                        style={{
                          background: "rgba(240,242,248,0.7)",
                          borderRadius: 14,
                        }}
                      >
                        <span
                          className="text-sm text-[#6b6b8a]"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
                          {item.label}
                        </span>
                        <span
                          className="font-semibold"
                          style={{
                            fontFamily: "var(--font-display)",
                            fontSize: 16,
                            color: item.color,
                          }}
                        >
                          {item.value}
                        </span>
                      </div>
                    ))}

                    {/* Speed gauge */}
                    <div className="mt-2">
                      <div
                        className="flex justify-between text-xs text-[#6b6b8a] mb-1"
                        style={{ fontFamily: "var(--font-mono)" }}
                      >
                        <span>0</span>
                        <span>현재 {road.speed}km/h</span>
                        <span>100</span>
                      </div>
                      <div
                        className="h-2 rounded-full"
                        style={{ background: "rgba(240,242,248,0.9)" }}
                      >
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, road.speed)}%`,
                            background: `linear-gradient(to right, ${
                              levelColor[
                                (road.level as keyof typeof levelColor) ||
                                  "yellow"
                              ]
                            }, ${
                              levelColor[
                                (road.level as keyof typeof levelColor) ||
                                  "yellow"
                              ]
                            }aa)`,
                          }}
                        />
                      </div>
                      <div
                        className="h-2 mt-1 rounded-full"
                        style={{ background: "rgba(240,242,248,0.9)" }}
                      >
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, road.avg)}%`,
                            background: "rgba(0,122,255,0.3)",
                          }}
                        />
                      </div>
                      <p
                        className="text-xs text-[#b0b0c8] mt-1"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        파란선: 평균 속도
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-[#6b6b8a] py-8 text-center">
                    선택 가능한 도로 정보가 없습니다.
                  </div>
                )}
              </div>
            </div>

            {/* Speed bar chart */}
            {roadSpeedData.length > 0 && (
              <div
                className="glass animate-slide-up-delay-3 p-5"
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
                  도로별 평균 속도
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={roadSpeedData}
                    margin={{ left: -20, right: 10 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(0,0,0,0.06)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="road"
                      tick={{
                        fontSize: 11,
                        fill: "#6b6b8a",
                        fontFamily: "var(--font-body)",
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
                      formatter={(value, name) => [
                        `${Number(value ?? 0)} km/h`,
                        name,
                      ]}
                    />
                    <Bar
                      dataKey="avg"
                      fill="#007aff"
                      opacity={0.3}
                      radius={[6, 6, 0, 0]}
                      name="평균"
                    />
                    <Bar
                      dataKey="speed"
                      radius={[6, 6, 0, 0]}
                      name="현재"
                      fill="#007aff"
                      label={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

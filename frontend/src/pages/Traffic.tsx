import { useState } from "react"
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
import { trafficTimeData, roadSpeedData } from "../data/mock"

const levelColor = { red: "#ff3b30", yellow: "#ff9500", green: "#34c759" }

export default function Traffic() {
  const [selectedRoad, setSelectedRoad] = useState("강변북로")
  const road = roadSpeedData.find((r) => r.road === selectedRoad)!

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0 px-4 md:px-8 pt-6">
        <h1
          className="text-[#1a1a2e] mb-1"
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: 26,
            letterSpacing: "-0.02em",
          }}
        >
          교통 분석
        </h1>
        <p
          className="text-[#6b6b8a] text-sm mb-5"
          style={{ fontFamily: "var(--font-body)" }}
        >
          시간대별 교통량 및 도로 속도 데이터
        </p>

        {/* Filters */}
        <div
          className="glass flex flex-wrap gap-2 p-3 mb-5"
          style={{ borderRadius: 18 }}
        >
          {["오늘", "어제", "1주일", "1개월"].map((t, i) => (
            <button
              key={t}
              className="px-3 py-1.5 text-xs font-medium transition-colors"
              style={{
                borderRadius: 10,
                background: i === 0 ? "rgba(0,122,255,0.12)" : "transparent",
                color: i === 0 ? "#007aff" : "#6b6b8a",
                fontFamily: "var(--font-body)",
              }}
            >
              {t}
            </button>
          ))}
          <div className="w-px bg-black/10 mx-1" />
          {["전체", "강변북로", "올림픽대로", "내부순환로", "경부고속"].map(
            (r, i) => (
              <button
                key={r}
                onClick={() => {
                  if (i > 0) setSelectedRoad(r)
                }}
                className="px-3 py-1.5 text-xs font-medium transition-colors"
                style={{
                  borderRadius: 10,
                  background:
                    (i === 0 && !selectedRoad) || selectedRoad === r
                      ? "rgba(0,122,255,0.12)"
                      : "transparent",
                  color:
                    (i === 0 && !selectedRoad) || selectedRoad === r
                      ? "#007aff"
                      : "#6b6b8a",
                  fontFamily: "var(--font-body)",
                }}
              >
                {r}
              </button>
            ),
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          {/* Volume chart */}
          <div className="glass lg:col-span-2 p-5" style={{ borderRadius: 20 }}>
            <h3
              className="text-[#1a1a2e] mb-4"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: 15,
              }}
            >
              시간대별 교통량
            </h3>
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
                  interval={2}
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
                <Line
                  type="monotone"
                  dataKey="volume"
                  stroke="#007aff"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, fill: "#007aff" }}
                />
              </LineChart>
            </ResponsiveContainer>
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
              {road.road}
            </h3>
            <div className="flex flex-col gap-3">
              {[
                {
                  label: "현재 속도",
                  value: `${road.speed} km/h`,
                  color: levelColor[(road.level as keyof typeof levelColor)],
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
                  color: levelColor[(road.level as keyof typeof levelColor)],
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
                      width: `${road.speed}%`,
                      background: `linear-gradient(to right, ${levelColor[(road.level as keyof typeof levelColor)]}, ${levelColor[(road.level as keyof typeof levelColor)]}aa)`,
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
                      width: `${road.avg}%`,
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
          </div>
        </div>

        {/* Speed bar chart */}
        <div className="glass p-5" style={{ borderRadius: 20 }}>
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
            <BarChart data={roadSpeedData} margin={{ left: -20, right: 10 }}>
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
      </main>
    </div>
  )
}

import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import NavBar from "../components/NavBar"

const features = [
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <circle cx="14" cy="14" r="11" stroke="#34c759" strokeWidth="1.8" />
        <path
          d="M8 14l4 4 8-8"
          stroke="#34c759"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    title: "실시간 교통 분석",
    desc: "서울시 제공 측정지점과 도로 링크의 교통 흐름을 한눈에 분석합니다.",
    color: "#34c759",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <path
          d="M14 4L5 22h18L14 4z"
          stroke="#ff3b30"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M14 12v5"
          stroke="#ff3b30"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <circle cx="14" cy="19.5" r="1" fill="#ff3b30" />
      </svg>
    ),
    title: "돌발상황 감지",
    desc: "사고·공사·통제 등 돌발상황을 즉시 포착해 경로에 반영합니다.",
    color: "#ff3b30",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <path
          d="M7 20a6 6 0 010-12A7.5 7.5 0 0121 11.5 5 5 0 0121 20H7z"
          stroke="#007aff"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M14 23v-3M11 22l1-2M17 22l-1-2"
          stroke="#007aff"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
    title: "기상 영향 분석",
    desc: "강수·안개·결빙 등 날씨 변수가 도로 속도에 미치는 영향을 분석합니다.",
    color: "#007aff",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <circle cx="14" cy="14" r="11" stroke="#5e5ce6" strokeWidth="1.8" />
        <path
          d="M8 17l4-6 3 3 3-5"
          stroke="#5e5ce6"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="22" cy="9" r="2" fill="#5e5ce6" />
      </svg>
    ),
    title: "AI 미래 교통량 예측",
    desc: "딥러닝 모델이 최대 3시간 후 교통량을 예측, 최적 출발 시점을 안내합니다.",
    color: "#5e5ce6",
  },
]

export default function Landing() {
  const navigate = useNavigate()
  const [origin, setOrigin] = useState("")
  const [dest, setDest] = useState("")
  const [timeMode, setTimeMode] = useState("now")
  const [departureAt, setDepartureAt] = useState("")
  const timeInputRef = useRef<HTMLInputElement>(null)

  const toLocalInput = (date: Date) => {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    return local.toISOString().slice(0, 16)
  }

  const selectOffset = (mode: string, minutes: number) => {
    setTimeMode(mode)
    setDepartureAt(minutes ? toLocalInput(new Date(Date.now() + minutes * 60_000)) : "")
  }

  const selectCustomTime = () => {
    setTimeMode("custom")
    if (!departureAt) setDepartureAt(toLocalInput(new Date(Date.now() + 30 * 60_000)))
    setTimeout(() => timeInputRef.current?.showPicker?.(), 0)
  }

  const analyze = () => {
    if (!origin.trim() || !dest.trim()) return
    const params = new URLSearchParams({ origin: origin.trim(), dest: dest.trim() })
    if (departureAt) params.set("departure", new Date(departureAt).toISOString())
    navigate(`/route?${params.toString()}`)
  }

  const handleSwap = () => {
    setOrigin(dest)
    setDest(origin)
  }

  return (
    <div
      className="min-h-full"
      style={{
        background:
          "linear-gradient(160deg, #e8edf5 0%, #dce3f0 60%, #e4e8f5 100%)",
      }}
    >
      <NavBar />

      {/* Hero */}
      <section
        className="relative min-h-screen flex flex-col items-center justify-center px-6 pb-16 overflow-hidden"
        style={{ paddingTop: "calc(env(safe-area-inset-top) + 96px)" }}
      >
        {/* Background abstract road network */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-25">
          <svg
            viewBox="0 0 1200 700"
            className="w-full h-full"
            preserveAspectRatio="xMidYMid slice"
          >
            {/* City grid lines */}
            {[80, 200, 320, 440, 560, 680, 800, 920, 1040].map((x) => (
              <line
                key={x}
                x1={x}
                y1={0}
                x2={x + 20}
                y2={700}
                stroke="#007aff"
                strokeWidth="1"
                opacity="0.4"
              />
            ))}
            {[60, 160, 260, 360, 460, 560].map((y) => (
              <line
                key={y}
                x1={0}
                y1={y}
                x2={1200}
                y2={y + 10}
                stroke="#34c759"
                strokeWidth="1"
                opacity="0.4"
              />
            ))}
            {/* Highlight roads */}
            <line
              x1="0"
              y1="220"
              x2="1200"
              y2="210"
              stroke="#ff9500"
              strokeWidth="3"
              opacity="0.5"
            />
            <line
              x1="0"
              y1="380"
              x2="1200"
              y2="370"
              stroke="#ff3b30"
              strokeWidth="4"
              opacity="0.5"
            />
            <line
              x1="440"
              y1="0"
              x2="430"
              y2="700"
              stroke="#007aff"
              strokeWidth="3"
              opacity="0.5"
            />
            {/* Han river */}
            <path
              d="M0 310 Q300 300 600 315 Q900 330 1200 310"
              stroke="rgba(100,160,240,0.6)"
              strokeWidth="28"
              fill="none"
            />
            {/* Pulse dots */}
            <circle cx="440" cy="220" r="8" fill="#ff3b30" opacity="0.7">
              <animate
                attributeName="r"
                values="6;14;6"
                dur="2.5s"
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values="0.7;0.1;0.7"
                dur="2.5s"
                repeatCount="indefinite"
              />
            </circle>
            <circle cx="800" cy="380" r="6" fill="#ff9500" opacity="0.7">
              <animate
                attributeName="r"
                values="4;12;4"
                dur="3s"
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values="0.7;0.1;0.7"
                dur="3s"
                repeatCount="indefinite"
              />
            </circle>
          </svg>
        </div>

        {/* Hero text */}
        <div className="relative z-10 text-center max-w-3xl fade-in">
          <div
            className="inline-flex items-center gap-2 px-4 py-1.5 mb-6 text-xs font-semibold"
            style={{
              background: "rgba(94,92,230,0.1)",
              color: "#5e5ce6",
              border: "1px solid rgba(94,92,230,0.25)",
              borderRadius: 20,
            }}
          >
            <span className="pulse-dot w-1.5 h-1.5 rounded-full bg-[#5e5ce6] inline-block" />
            UI 프로토타입 · API 연동 예정
          </div>

          <h1
            className="mb-4 leading-tight text-[#1a1a2e]"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "clamp(48px, 6vw, 80px)",
              letterSpacing: "-0.03em",
            }}
          >
            RoadPulse
          </h1>
          <p
            className="mb-2 text-[#4a4a68]"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 500,
              fontSize: "clamp(22px, 3vw, 32px)",
              letterSpacing: "-0.01em",
            }}
          >
            도시의 흐름을 읽다
          </p>
          <p
            className="mb-10 text-base text-[#6b6b8a] max-w-xl mx-auto leading-relaxed"
            style={{ fontFamily: "var(--font-body)" }}
          >
            실시간 교통량, 돌발상황, 날씨와 AI 예측 데이터를 결합해
            <br className="hidden sm:block" />더 빠르고 안정적인 이동 경로를
            찾아드립니다.
          </p>

          {/* Route search card */}
          <div
            className="glass mx-auto max-w-xl p-5 fade-in"
            style={{ borderRadius: 28 }}
          >
            <div className="relative flex flex-col gap-2">
              <div className="relative flex flex-col gap-2">
              {/* Origin */}
              <div className="relative">
                <div
                  className="absolute left-4 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2"
                  style={{ borderColor: "#007aff", background: "white" }}
                />
                <input
                  className="w-full pl-10 pr-4 py-3.5 text-sm outline-none placeholder:text-[#b0b0c8]"
                  style={{
                    background: "rgba(240,242,248,0.8)",
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  placeholder="출발지를 입력하세요"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                />
                <button
                  type="button"
                  aria-label="현재 위치 사용"
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-xl text-[#007aff] hover:bg-[rgba(0,122,255,0.1)] transition-colors text-xs font-medium"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  현위치
                </button>
              </div>

              {/* Swap button: 두 입력칸 경계에 고정 */}
              <button
                type="button"
                aria-label="출발지와 도착지 바꾸기"
                onClick={handleSwap}
                className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center hover:scale-105 transition-transform z-10 shadow-sm"
                style={{
                  background: "rgba(255,255,255,0.9)",
                  border: "1px solid rgba(0,122,255,0.2)",
                  borderRadius: 10,
                  color: "#007aff",
                }}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M7 2v10M4 9l3 3 3-3M4 5l3-3 3 3"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              {/* Destination */}
              <div className="relative">
                <div
                  className="absolute left-4 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-sm"
                  style={{ background: "#5e5ce6" }}
                />
                <input
                  className="w-full pl-10 pr-4 py-3.5 text-sm outline-none placeholder:text-[#b0b0c8]"
                  style={{
                    background: "rgba(240,242,248,0.8)",
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.9)",
                    fontFamily: "var(--font-body)",
                    color: "#1a1a2e",
                  }}
                  placeholder="도착지를 입력하세요"
                  value={dest}
                  onChange={(e) => setDest(e.target.value)}
                />
              </div>
              </div>

              {/* Time selector */}
              <div className="flex gap-2 mt-1">
                {[
                  { mode: "now", label: "지금 출발", minutes: 0 },
                  { mode: "30m", label: "+30분", minutes: 30 },
                  { mode: "1h", label: "+1시간", minutes: 60 },
                ].map((option) => (
                  <button
                    key={option.mode}
                    type="button"
                    onClick={() => selectOffset(option.mode, option.minutes)}
                    className="flex-1 py-2 text-xs font-medium transition-all"
                    style={{
                      borderRadius: 12,
                      background:
                        timeMode === option.mode
                          ? "rgba(0,122,255,0.12)"
                          : "rgba(240,242,248,0.8)",
                      color: timeMode === option.mode ? "#007aff" : "#6b6b8a",
                      border: `1px solid ${
                        timeMode === option.mode
                          ? "rgba(0,122,255,0.3)"
                          : "rgba(255,255,255,0.9)"
                      }`,
                      fontFamily: "var(--font-body)",
                    }}
                  >
                    {option.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={selectCustomTime}
                  className="flex-1 py-2 text-xs font-medium transition-all"
                  style={{
                    borderRadius: 12,
                    background: timeMode === "custom" ? "rgba(0,122,255,0.12)" : "rgba(240,242,248,0.8)",
                    color: timeMode === "custom" ? "#007aff" : "#6b6b8a",
                    border: `1px solid ${timeMode === "custom" ? "rgba(0,122,255,0.3)" : "rgba(255,255,255,0.9)"}`,
                  }}
                >시간 선택</button>
              </div>

              {timeMode === "custom" && (
                <div className="rounded-xl bg-white/70 px-3 py-2 text-left">
                  <label htmlFor="departure-time" className="block text-[11px] text-[#6b6b8a] mb-1">원하는 출발 시간 (최대 3시간 후)</label>
                  <input
                    ref={timeInputRef}
                    id="departure-time"
                    type="datetime-local"
                    min={toLocalInput(new Date())}
                    max={toLocalInput(new Date(Date.now() + 3 * 60 * 60_000))}
                    value={departureAt}
                    onChange={(e) => setDepartureAt(e.target.value)}
                    className="w-full bg-transparent text-sm text-[#1a1a2e] outline-none"
                  />
                </div>
              )}

              <button
                onClick={analyze}
                disabled={!origin.trim() || !dest.trim()}
                className="w-full py-3.5 font-semibold text-white mt-1 transition-all hover:opacity-90 active:scale-98 disabled:opacity-50"
                style={{
                  borderRadius: 18,
                  background:
                    "linear-gradient(135deg, #007aff 0%, #5e5ce6 100%)",
                  fontFamily: "var(--font-display)",
                  fontSize: 15,
                  letterSpacing: "-0.01em",
                }}
              >
                ✦ AI 경로 분석
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section className="px-6 pb-24 max-w-5xl mx-auto">
        <div className="text-center mb-10">
          <h2
            className="text-[#1a1a2e] mb-2"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "clamp(26px, 3vw, 36px)",
              letterSpacing: "-0.02em",
            }}
          >
            RoadPulse가 다른 이유
          </h2>
          <p
            className="text-[#6b6b8a] text-sm"
            style={{ fontFamily: "var(--font-body)" }}
          >
            단순 내비게이션이 아닙니다 — 도시 전체의 흐름을 예측합니다.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="glass p-6 hover:scale-[1.02] transition-transform cursor-default"
              style={{ borderRadius: 24 }}
            >
              <div
                className="w-12 h-12 flex items-center justify-center mb-4"
                style={{
                  background: `${f.color}18`,
                  borderRadius: 14,
                  border: `1px solid ${f.color}30`,
                }}
              >
                {f.icon}
              </div>
              <h3
                className="mb-2 text-[#1a1a2e]"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: 16,
                }}
              >
                {f.title}
              </h3>
              <p
                className="text-[#6b6b8a] text-sm leading-relaxed"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

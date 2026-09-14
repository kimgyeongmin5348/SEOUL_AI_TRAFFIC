import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import NavBar from "../components/NavBar"
import { reverseGeocodeCurrentLocation } from "../services/placeSearch"

const features = [
  {
    icon: "🟢",
    title: "실시간 교통 분석",
    desc: "서울시 전 구간 도로 속도·교통량을 실시간 측정, 초 단위 업데이트.",
    color: "#34c759",
  },
  {
    icon: "🔴",
    title: "돌발상황 감지",
    desc: "사고·공사·통제 등 돌발상황을 즉시 포착해 경로에 반영합니다.",
    color: "#ff3b30",
  },
  {
    icon: "🌤",
    title: "기상 영향 분석",
    desc: "강수·안개·결빙 등 날씨 변수가 도로 속도에 미치는 영향을 분석합니다.",
    color: "#34aadc",
  },
  {
    icon: "✦",
    title: "AI 미래 교통량 예측",
    desc: "딥러닝 모델이 최대 3시간 후 교통량을 예측, 최적 출발 시점을 안내합니다.",
    color: "#5856d6",
  },
]

export default function Landing() {
  const navigate = useNavigate()
  const [origin, setOrigin] = useState("")
  const [dest, setDest] = useState("")
  const [timeMode, setTimeMode] = useState("now")
  const [departureAt, setDepartureAt] = useState("")
  const [locating, setLocating] = useState(false)
  const [locationMessage, setLocationMessage] = useState("")
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

  const useCurrentLocation = () => {
    if (!window.isSecureContext || !navigator.geolocation) {
      setLocationMessage("위치 기능은 HTTPS 또는 localhost에서 사용할 수 있습니다.")
      return
    }
    setLocating(true)
    setLocationMessage("현재 위치를 확인하고 있습니다…")
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      try {
        const place = await reverseGeocodeCurrentLocation(coords.latitude, coords.longitude)
        const roadName = place.roadAddress || place.address || place.name
        setOrigin(roadName)
        setLocationMessage(`${roadName} · 도로명 확인 완료`)
      } catch (err) {
        setLocationMessage(err instanceof Error && err.message === "OUTSIDE_SEOUL"
          ? "현 위치가 서울이 아닙니다. 현위치로부터 경로설정을 사용하지 못합니다."
          : "현재 위치의 도로명 주소를 확인하지 못했습니다.")
      } finally {
        setLocating(false)
      }
    }, () => {
      setLocating(false)
      setLocationMessage("현재 위치를 확인할 수 없습니다. 위치 권한을 확인해 주세요.")
    }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60_000 })
  }

  return (
    <div className="min-h-full" style={{ position: "relative" }}>
      {/* Full-bleed Seoul night photo */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `url("https://images.unsplash.com/photo-1555425293-16e3d1e49b85?w=1920&h=1080&fit=crop&auto=format")`,
          backgroundSize: "cover",
          backgroundPosition: "center top",
          zIndex: 0,
        }}
      />
      {/* Dark overlay for hero readability */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{ background: "rgba(10,12,24,0.58)", zIndex: 1 }}
      />

      <NavBar />

      {/* Hero */}
      <section
        className="relative flex flex-col items-center justify-center min-h-screen px-4 sm:px-6 pb-16"
        style={{ zIndex: 2, paddingTop: "calc(env(safe-area-inset-top) + 96px)" }}
      >
        <div className="text-center max-w-3xl fade-in">
          {/* Status badge */}
          <div
            className="inline-flex items-center gap-2 px-4 py-1.5 mb-7 text-xs font-semibold"
            style={{
              background: "rgba(255,255,255,0.1)",
              color: "rgba(255,255,255,0.9)",
              border: "1px solid rgba(255,255,255,0.18)",
              borderRadius: 20,
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <span className="pulse-dot w-2 h-2 rounded-full bg-[#34c759] inline-block shadow-[0_0_8px_#34c759]" />
            실시간 업데이트 중 · 서울시 전 구간
          </div>

          <h1
            className="mb-3 text-white"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "clamp(52px, 7vw, 88px)",
              letterSpacing: "-0.035em",
              lineHeight: 1.05,
              textShadow: "0 2px 32px rgba(0,0,0,0.5)",
            }}
          >
            RoadPulse
          </h1>
          <p
            className="mb-2"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 400,
              fontSize: "clamp(20px, 2.5vw, 28px)",
              color: "rgba(255,255,255,0.85)",
              letterSpacing: "-0.01em",
            }}
          >
            도시의 흐름을 읽다
          </p>
          <p
            className="mb-10 text-sm leading-relaxed max-w-xl mx-auto"
            style={{ color: "rgba(255,255,255,0.6)", fontFamily: "var(--font-body)" }}
          >
            실시간 교통량, 돌발상황, 날씨와 AI 예측 데이터를 결합해
            <br className="hidden sm:block" />
            더 빠르고 안정적인 이동 경로를 찾아드립니다.
          </p>

          {/* Route search — Liquid Glass card on dark photo */}
          <div
            className="mx-auto max-w-xl p-5 sm:p-6 fade-in"
            style={{
              borderRadius: 28,
              background: "rgba(255,255,255,0.12)",
              backdropFilter: "blur(48px) saturate(1.8)",
              WebkitBackdropFilter: "blur(48px) saturate(1.8)",
              border: "1px solid rgba(255,255,255,0.22)",
              boxShadow: "0 16px 48px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.2) inset",
            }}
          >
            <div className="relative flex flex-col gap-2.5">
              {/* Origin & Destination wrapper */}
              <div className="relative flex flex-col gap-2">
                {/* Origin */}
                <div className="relative">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-white/80 bg-transparent" />
                  <input
                    className="w-full pl-10 pr-24 py-3.5 text-sm outline-none placeholder:text-white/40 transition-colors focus:border-white/40"
                    style={{
                      background: "rgba(255,255,255,0.1)",
                      borderRadius: 16,
                      border: "1px solid rgba(255,255,255,0.15)",
                      fontFamily: "var(--font-body)",
                      color: "white",
                    }}
                    placeholder="출발지를 입력하세요"
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && analyze()}
                  />
                  <button
                    type="button"
                    onClick={useCurrentLocation}
                    disabled={locating}
                    className="absolute right-3 top-1/2 -translate-y-1/2 px-2.5 py-1 text-xs font-medium rounded-xl transition-all active:scale-95 disabled:opacity-50"
                    style={{
                      background: "rgba(255,255,255,0.16)",
                      color: "rgba(255,255,255,0.9)",
                      fontFamily: "var(--font-body)",
                      border: "1px solid rgba(255,255,255,0.2)",
                    }}
                  >
                    {locating ? "확인 중…" : "현위치"}
                  </button>
                </div>

                {/* Swap */}
                <button
                  type="button"
                  onClick={handleSwap}
                  aria-label="출발지와 도착지 바꾸기"
                  className="absolute right-4 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center hover:scale-110 active:scale-95 transition-transform z-10 shadow-sm"
                  style={{
                    background: "rgba(255,255,255,0.2)",
                    border: "1px solid rgba(255,255,255,0.25)",
                    borderRadius: 9,
                    color: "rgba(255,255,255,0.9)",
                  }}
                >
                  <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
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
                    style={{ background: "rgba(88,86,214,0.9)" }}
                  />
                  <input
                    className="w-full pl-10 pr-4 py-3.5 text-sm outline-none placeholder:text-white/40 transition-colors focus:border-white/40"
                    style={{
                      background: "rgba(255,255,255,0.1)",
                      borderRadius: 16,
                      border: "1px solid rgba(255,255,255,0.15)",
                      fontFamily: "var(--font-body)",
                      color: "white",
                    }}
                    placeholder="도착지를 입력하세요"
                    value={dest}
                    onChange={(e) => setDest(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && analyze()}
                  />
                </div>
              </div>

              {locationMessage && (
                <p role="status" className="px-1 text-left text-xs text-white/75 fade-in">
                  {locationMessage}
                </p>
              )}

              {/* Time */}
              <div className="flex gap-2 mt-1">
                {[
                  { mode: "now", label: "지금 출발", minutes: 0 },
                  { mode: "30m", label: "+30분", minutes: 30 },
                  { mode: "1h", label: "+1시간", minutes: 60 },
                ].map((t) => (
                  <button
                    key={t.mode}
                    type="button"
                    onClick={() => selectOffset(t.mode, t.minutes)}
                    className="flex-1 py-2 text-xs font-medium transition-all hover:opacity-90"
                    style={{
                      borderRadius: 12,
                      background:
                        timeMode === t.mode ? "rgba(88,86,214,0.5)" : "rgba(255,255,255,0.08)",
                      color: timeMode === t.mode ? "white" : "rgba(255,255,255,0.65)",
                      border: `1px solid ${
                        timeMode === t.mode
                          ? "rgba(88,86,214,0.65)"
                          : "rgba(255,255,255,0.12)"
                      }`,
                      fontFamily: "var(--font-body)",
                      boxShadow:
                        timeMode === t.mode ? "0 2px 10px rgba(88,86,214,0.3)" : "none",
                    }}
                  >
                    {t.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={selectCustomTime}
                  className="flex-1 py-2 text-xs font-medium transition-all hover:opacity-90"
                  style={{
                    borderRadius: 12,
                    background:
                      timeMode === "custom" ? "rgba(88,86,214,0.5)" : "rgba(255,255,255,0.08)",
                    color: timeMode === "custom" ? "white" : "rgba(255,255,255,0.65)",
                    border: `1px solid ${
                      timeMode === "custom"
                        ? "rgba(88,86,214,0.65)"
                        : "rgba(255,255,255,0.12)"
                    }`,
                    fontFamily: "var(--font-body)",
                    boxShadow:
                      timeMode === "custom" ? "0 2px 10px rgba(88,86,214,0.3)" : "none",
                  }}
                >
                  시간 선택
                </button>
              </div>

              {/* Custom time picker */}
              {timeMode === "custom" && (
                <div
                  className="rounded-2xl p-3 text-left fade-in"
                  style={{
                    background: "rgba(255,255,255,0.08)",
                    border: "1px solid rgba(255,255,255,0.15)",
                  }}
                >
                  <label
                    htmlFor="departure-time"
                    className="block text-[11px] text-white/70 mb-1"
                  >
                    원하는 출발 시간 (최대 3시간 후)
                  </label>
                  <input
                    ref={timeInputRef}
                    id="departure-time"
                    type="datetime-local"
                    min={toLocalInput(new Date())}
                    max={toLocalInput(new Date(Date.now() + 3 * 60 * 60_000))}
                    value={departureAt}
                    onChange={(e) => setDepartureAt(e.target.value)}
                    className="w-full bg-transparent text-sm text-white outline-none [color-scheme:dark]"
                  />
                </div>
              )}

              <button
                type="button"
                onClick={analyze}
                disabled={!origin.trim() || !dest.trim()}
                className="w-full py-3.5 font-semibold text-white mt-1 transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  borderRadius: 18,
                  background: "linear-gradient(135deg, #5856d6 0%, #34aadc 100%)",
                  fontFamily: "var(--font-display)",
                  fontSize: 15,
                  letterSpacing: "-0.01em",
                  boxShadow: "0 4px 20px rgba(88,86,214,0.5)",
                }}
              >
                ✦ AI 경로 분석
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature cards — dark glass section over photo */}
      <section
        className="relative px-4 sm:px-6 pb-24 max-w-5xl mx-auto"
        style={{ zIndex: 2 }}
      >
        <div className="text-center mb-10">
          <h2
            className="text-white mb-2"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "clamp(24px, 3vw, 34px)",
              letterSpacing: "-0.02em",
              textShadow: "0 2px 16px rgba(0,0,0,0.4)",
            }}
          >
            RoadPulse가 다른 이유
          </h2>
          <p
            style={{
              color: "rgba(255,255,255,0.6)",
              fontSize: 14,
              fontFamily: "var(--font-body)",
            }}
          >
            단순 내비게이션이 아닙니다 — 도시 전체의 흐름을 예측합니다.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="p-6 cursor-default"
              style={{
                borderRadius: 24,
                background: "rgba(255,255,255,0.1)",
                backdropFilter: "blur(40px) saturate(1.6)",
                WebkitBackdropFilter: "blur(40px) saturate(1.6)",
                border: "1px solid rgba(255,255,255,0.18)",
                boxShadow:
                  "0 4px 24px rgba(0,0,0,0.2), 0 1px 0 rgba(255,255,255,0.15) inset",
              }}
            >
              <div
                className="w-11 h-11 flex items-center justify-center text-xl mb-4"
                style={{
                  background: `${f.color}22`,
                  borderRadius: 13,
                  border: `1px solid ${f.color}40`,
                }}
              >
                {f.icon}
              </div>
              <h3
                className="mb-2 text-white"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: 15,
                }}
              >
                {f.title}
              </h3>
              <p
                style={{
                  color: "rgba(255,255,255,0.6)",
                  fontSize: 13,
                  lineHeight: 1.6,
                  fontFamily: "var(--font-body)",
                }}
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

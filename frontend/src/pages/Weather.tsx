import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import { fetchWeatherData } from "../services/api"
import { useState, useEffect } from "react"

const impactColor = { low: "#34c759", medium: "#ff9500", high: "#ff3b30" }

const SEOUL_DISTRICTS = [
  "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
  "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
  "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
  "서초구", "강남구", "송파구", "강동구",
]

interface WeatherInfo {
  station: string
  temp: number
  feelsLike: number
  humidity: number
  windSpeed: number
  pressure: number
  precipitation: number
  condition: string
  icon: string
  trafficImpact: "low" | "medium" | "high"
  trafficMessage: string
}

export default function Weather() {
  const [districtIndex, setDistrictIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [weatherState, setWeatherState] = useState<{
    weather: WeatherInfo | null
    history: { time: string; temp: number; humidity: number; rain: number }[]
    latestAt: string | null
    isFromDb: boolean
  }>({
    weather: null,
    history: [],
    latestAt: null,
    isFromDb: false,
  })

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchWeatherData()
      .then((res) => {
        if (active) {
          setWeatherState(res)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setDistrictIndex((index) => (index + 1) % SEOUL_DISTRICTS.length)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [])

  const w = weatherState.weather
  const district = SEOUL_DISTRICTS[districtIndex]

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
            기상 정보
          </h1>
          <div className="flex items-center gap-2 mb-5">
            <p
              className="text-white/70 text-sm"
              style={{ fontFamily: "var(--font-body)" }}
            >
              교통에 영향을 주는 기상 변수 분석 · 서울 25개 구 자동 순환
            </p>
            {weatherState.isFromDb && (
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
            {weatherState.latestAt && (
              <span
                className="text-xs text-[#6b6b8a]"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                관측: {new Date(weatherState.latestAt).toLocaleDateString("ko-KR", {
                  month: "short",
                  day: "numeric",
                })} {new Date(weatherState.latestAt).toLocaleTimeString("ko-KR", {
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
            <div className="w-8 h-8 rounded-full border-2 border-[#007aff] border-t-transparent animate-spin" />
            <p
              className="text-white/80 text-sm font-medium"
              style={{ fontFamily: "var(--font-body)" }}
            >
              실시간 DB 기상 데이터를 수신 중입니다...
            </p>
          </div>
        ) : !w ? (
          <div className="glass p-12 text-center my-8" style={{ borderRadius: 20 }}>
            <p
              className="text-white/80 text-base font-semibold mb-1"
              style={{ fontFamily: "var(--font-display)" }}
            >
              DB에 저장된 기상 관측 데이터가 없습니다.
            </p>
            <p className="text-white/50 text-xs" style={{ fontFamily: "var(--font-body)" }}>
              기상청 관측망 수집 상태를 확인해 주세요.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 animate-slide-up-delay-1">
            {/* Current weather card */}
            <div
              key={district}
              className="lg:col-span-1 p-6 text-white weather-district-card cursor-default"
              style={{
                borderRadius: 24,
                background: "linear-gradient(160deg, #007aff 0%, #5e5ce6 100%)",
                boxShadow: "0 12px 40px rgba(0,122,255,0.3)",
              }}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p
                    className="text-white/70 text-sm mb-1"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    {district}
                  </p>
                  <p className="text-[11px] text-white/60 mb-2">
                    {w.station} 대표 관측 · 3초마다 다음 구
                  </p>
                  <p
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 800,
                      fontSize: 64,
                      letterSpacing: "-0.03em",
                      lineHeight: 1,
                    }}
                  >
                    {w.temp}°
                  </p>
                  <p
                    className="text-white/80 mt-1"
                    style={{ fontFamily: "var(--font-body)", fontSize: 14 }}
                  >
                    체감 {w.feelsLike}° · {w.condition}
                  </p>
                </div>
                <span style={{ fontSize: 56 }}>{w.icon}</span>
              </div>

              <div
                className="p-3 rounded-xl mb-4"
                style={{ background: "rgba(255,255,255,0.15)" }}
              >
                <p
                  className="text-sm font-medium text-white mb-1"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  교통 영향도
                </p>
                <div className="flex items-center gap-2">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ background: impactColor[w.trafficImpact] }}
                  />
                  <p
                    className="text-xs text-white/90"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    {w.trafficMessage}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "습도", value: `${w.humidity}%` },
                  { label: "풍속", value: `${w.windSpeed}m/s` },
                  { label: "강수량", value: `${w.precipitation}mm` },
                  { label: "기압", value: `${w.pressure}hPa` },
                ].map((item) => (
                  <div key={item.label} className="flex flex-col">
                    <span
                      className="text-white/60 text-xs"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {item.label}
                    </span>
                    <span
                      className="text-white font-medium text-sm"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
              <div
                className="mt-4 flex items-center gap-1"
                aria-label={`서울 자치구 ${districtIndex + 1}/${SEOUL_DISTRICTS.length}`}
              >
                {SEOUL_DISTRICTS.map((name, index) => (
                  <button
                    type="button"
                    key={name}
                    aria-label={`${name} 보기`}
                    onClick={() => setDistrictIndex(index)}
                    className="h-1 flex-1 rounded-full transition-all duration-300"
                    style={{
                      background:
                        index === districtIndex
                          ? "white"
                          : "rgba(255,255,255,.25)",
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Weather impact cards */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              <div
                className="p-5 glass"
                style={{
                  borderRadius: 22,
                }}
              >
                <h3
                  className="text-sm font-semibold text-[#1a1a2e] mb-2"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  🌧 강수와 제동 거리
                </h3>
                <p
                  className="text-xs text-[#6b6b8a] leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  강수량이 증가하면 노면 마찰계수가 감소하여 제동거리가 최대 1.8배 길어집니다.
                  안전거리를 평소보다 2배 이상 확보하세요.
                </p>
              </div>
              <div
                className="p-5 glass"
                style={{
                  borderRadius: 22,
                }}
              >
                <h3
                  className="text-sm font-semibold text-[#1a1a2e] mb-2"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  💨 풍속과 교량/고가 주행
                </h3>
                <p
                  className="text-xs text-[#6b6b8a] leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  현재 관측 풍속은 {w.windSpeed}m/s입니다. 한강 교량 및 고가도로 통과 시 횡풍에 유의하여 서행 운전하시기 바랍니다.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

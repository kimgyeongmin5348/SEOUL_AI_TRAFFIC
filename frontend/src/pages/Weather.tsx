import Sidebar from "../components/Sidebar"
import { weatherData as defaultWeatherData } from "../data/mock"
import { fetchWeatherData } from "../services/api"
import { useState, useEffect } from "react"

const impactColor = { low: "#34c759", medium: "#ff9500", high: "#ff3b30" }
const impactLabel = { low: "영향 낮음", medium: "주의", high: "영향 높음" }

const SEOUL_DISTRICTS = [
  "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
  "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
  "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
  "서초구", "강남구", "송파구", "강동구",
]

type WeatherInfo = Omit<typeof defaultWeatherData, "trafficImpact"> & {
  trafficImpact: "low" | "medium" | "high"
}

export default function Weather() {
  const [districtIndex, setDistrictIndex] = useState(0)
  const [weatherState, setWeatherState] = useState<{
    weather: WeatherInfo
    history: { time: string; temp: number; humidity: number; rain: number }[]
    latestAt: string | null
    isFromDb: boolean
  }>({
    weather: defaultWeatherData as WeatherInfo,
    history: [],
    latestAt: null,
    isFromDb: false,
  })

  useEffect(() => {
    let active = true
    fetchWeatherData().then((res) => {
      if (active) {
        setWeatherState(res)
      }
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
          기상 정보
        </h1>
        <div className="flex items-center gap-2 mb-5">
          <p
            className="text-[#6b6b8a] text-sm"
            style={{ fontFamily: "var(--font-body)" }}
          >
            교통에 영향을 주는 기상 변수 분석 · 서울 25개 구 자동 순환
          </p>
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
            style={{
              background: weatherState.isFromDb
                ? "rgba(52,199,89,0.12)"
                : "rgba(94,92,230,0.12)",
              color: weatherState.isFromDb ? "#248a3d" : "#5e5ce6",
              fontFamily: "var(--font-body)",
            }}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                weatherState.isFromDb ? "bg-[#34c759]" : "bg-[#5e5ce6]"
              }`}
            />
            {weatherState.isFromDb ? "DB 실시간 연동" : "예시 데이터"}
          </span>
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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Current weather card */}
          <div
            key={district}
            className="lg:col-span-1 p-6 text-white weather-district-card"
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
                <p className="text-[11px] text-white/60 mb-2">{w.station} 대표 관측 · 3초마다 다음 구</p>
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
                { label: "풍속", value: `${w.windSpeed}m/s ${w.windDir}` },
                { label: "강수량", value: `${w.precipitation}mm` },
                { label: "기압", value: `${w.pressure}hPa` },
                { label: "시정", value: `${w.visibility}km` },
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
            <div className="mt-4 flex items-center gap-1" aria-label={`서울 자치구 ${districtIndex + 1}/${SEOUL_DISTRICTS.length}`}>
              {SEOUL_DISTRICTS.map((name, index) => (
                <button
                  type="button"
                  key={name}
                  aria-label={`${name} 보기`}
                  onClick={() => setDistrictIndex(index)}
                  className="h-1 flex-1 rounded-full transition-all duration-300"
                  style={{ background: index === districtIndex ? "white" : "rgba(255,255,255,.25)" }}
                />
              ))}
            </div>
          </div>

          {/* Forecast */}
          <div className="lg:col-span-2 glass p-5" style={{ borderRadius: 24 }}>
            <h3
              className="text-[#1a1a2e] mb-4"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: 16,
              }}
            >
              시간대별 예보 · 교통 영향
            </h3>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {w.forecast.map((f) => {
                const color = impactColor[f.trafficImpact]
                return (
                  <div
                    key={f.time}
                    className="flex-shrink-0 flex flex-col items-center gap-2 p-4"
                    style={{
                      background: "rgba(240,242,248,0.7)",
                      borderRadius: 18,
                      minWidth: 100,
                    }}
                  >
                    <span
                      className="text-xs font-medium text-[#6b6b8a]"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {f.time}
                    </span>
                    <span style={{ fontSize: 28 }}>{f.condition}</span>
                    <span
                      className="font-semibold text-[#1a1a2e]"
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: 18,
                      }}
                    >
                      {f.temp}°
                    </span>
                    <div className="flex flex-col items-center gap-1">
                      <span
                        className="text-xs text-[#6b6b8a]"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        강수 {f.precipitation}%
                      </span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{
                          background: `${color}18`,
                          color,
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        {impactLabel[f.trafficImpact]}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Weather metrics for traffic */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div
                className="p-4"
                style={{
                  background: "rgba(240,242,248,0.7)",
                  borderRadius: 18,
                }}
              >
                <h4
                  className="text-sm font-semibold text-[#1a1a2e] mb-3"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  🌧 강수와 교통 속도
                </h4>
                <p
                  className="text-xs text-[#6b6b8a] leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  강수량이 증가하면 제동거리와 평균 주행속도에 영향을 줄 수
                  있습니다. 실제 수집 데이터로 영향도를 분석해 안내할
                  예정입니다.
                </p>
              </div>
              <div
                className="p-4"
                style={{
                  background: "rgba(240,242,248,0.7)",
                  borderRadius: 18,
                }}
              >
                <h4
                  className="text-sm font-semibold text-[#1a1a2e] mb-3"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  💨 풍속과 고가도로
                </h4>
                <p
                  className="text-xs text-[#6b6b8a] leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  현재 예시 풍속은 {w.windSpeed}m/s입니다. 고가도로와 교량
                  구간의 영향도는 실제 관측 데이터 연동 후 제공합니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

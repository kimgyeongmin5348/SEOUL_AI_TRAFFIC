import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import SubpageBackground from "../components/SubpageBackground"
import { Link } from "react-router-dom"
import NavBar from "../components/NavBar"
import { reverseGeocodeCurrentLocation } from "../services/placeSearch"

const features = [
  { number: "01", title: "실시간 교통", desc: "주요 도로의 속도와 혼잡도를 한눈에 확인하세요.", href: "/traffic", tag: "TRAFFIC" },
  { number: "02", title: "돌발상황 확인", desc: "사고, 공사, 통제 정보를 출발 전에 살펴보세요.", href: "/incidents", tag: "INCIDENTS" },
  { number: "03", title: "기상 영향 분석", desc: "날씨가 이동에 미치는 영향을 함께 확인하세요.", href: "/weather", tag: "WEATHER" },
  { number: "04", title: "AI 교통 예측", desc: "앞으로의 도로 상황을 살펴보고 출발을 계획하세요.", href: "/prediction", tag: "PREDICTION" },
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
    <div className="landing-page">
      <SubpageBackground />
      <NavBar />
      <main className="landing-content">
        <section className="landing-hero">
          <div className="hero-copy animate-slide-up">
            <div className="eyebrow"><span /> SEOUL MOBILITY INTELLIGENCE</div>
            <h1>도시의 흐름을 읽고,<br /><span>이동의 여유를 찾다.</span></h1>
            <p className="hero-description">복잡한 서울의 길, 더 명확한 선택.<br />실시간 교통과 날씨, AI 예측을 연결해<br className="sm:hidden" /> 더 나은 이동을 계획하세요.</p>
            <Link to="/dashboard" className="hero-map-link">실시간 교통 지도 살펴보기 <span aria-hidden="true">↗</span></Link>
            <div className="hero-context">
              <div><span className="context-label">COVERAGE</span><strong>서울 전역</strong></div>
              <div><span className="context-label">INSIGHT</span><strong>교통 · 기상 · 돌발</strong></div>
              <div><span className="context-label">POWERED BY</span><strong>AI 교통 예측</strong></div>
            </div>
          </div>
          <form className="route-planner animate-slide-up-delay-1" onSubmit={(event) => { event.preventDefault(); analyze() }}>
            <div className="planner-heading"><span className="planner-kicker">PLAN YOUR JOURNEY</span><span className="planner-ai">✦ AI 경로 분석</span></div>
            <h2>어디로 이동하시나요?</h2>
            <p className="planner-description">출발지와 도착지를 입력하고 경로를 확인하세요.</p>
            <div className="planner-fields">
              <label className="planner-field" htmlFor="route-origin">
                <span className="field-marker origin-marker" />
                <span className="field-content"><span className="field-label">출발지</span><input id="route-origin" placeholder="출발지를 입력하세요" value={origin} onChange={(event) => setOrigin(event.target.value)} required /></span>
                <button type="button" className="location-button" onClick={useCurrentLocation} disabled={locating}>{locating ? "확인 중…" : "현위치"}</button>
              </label>
              <div className="planner-connector"><span /><button type="button" onClick={handleSwap} aria-label="출발지와 도착지 바꾸기">↓↑</button></div>
              <label className="planner-field" htmlFor="route-destination">
                <span className="field-marker destination-marker" />
                <span className="field-content"><span className="field-label">도착지</span><input id="route-destination" placeholder="어디로 갈까요?" value={dest} onChange={(event) => setDest(event.target.value)} required /></span>
              </label>
            </div>
            {locationMessage && <p role="status" className="planner-message">{locationMessage}</p>}
            <div className="departure-heading"><span>출발 시간</span><span>최대 3시간 후</span></div>
            <div className="departure-options">
              {[{ mode: "now", label: "지금 출발", minutes: 0 }, { mode: "30m", label: "+30분", minutes: 30 }, { mode: "1h", label: "+1시간", minutes: 60 }].map((item) => (
                <button key={item.mode} type="button" aria-pressed={timeMode === item.mode} onClick={() => selectOffset(item.mode, item.minutes)}>{item.label}</button>
              ))}
              <button type="button" aria-pressed={timeMode === "custom"} onClick={selectCustomTime}>시간 선택</button>
            </div>
            {timeMode === "custom" && <div className="custom-departure"><label htmlFor="departure-time">원하는 출발 시간</label><input ref={timeInputRef} id="departure-time" type="datetime-local" min={toLocalInput(new Date())} max={toLocalInput(new Date(Date.now() + 3 * 60 * 60_000))} value={departureAt} onChange={(event) => setDepartureAt(event.target.value)} required /></div>}
            <button type="submit" className="planner-submit" disabled={!origin.trim() || !dest.trim()}>AI로 이동 경로 분석하기 <span aria-hidden="true">→</span></button>
            <p className="planner-footnote">교통 · 돌발상황 · 기상 정보를 함께 고려합니다</p>
          </form>
        </section>
        <section className="landing-features" aria-labelledby="features-title">
          <div className="features-heading"><div><span className="eyebrow">A BETTER WAY TO MOVE</span><h2 id="features-title">이동에 필요한 모든 인사이트</h2></div><p>흩어진 도로 정보를 한곳에서.</p></div>
          <div className="feature-grid">{features.map((feature) => <Link key={feature.href} to={feature.href} className="feature-card"><div className="feature-top"><span>{feature.number} / {feature.tag}</span><span aria-hidden="true">↗</span></div><h3>{feature.title}</h3><p>{feature.desc}</p></Link>)}</div>
        </section>
        <footer className="landing-footer"><span className="footer-brand">RoadPulse<span> 서울의 흐름을 연결하다.</span></span><span>SEOUL · SOUTH KOREA</span></footer>
      </main>
    </div>
  )
}

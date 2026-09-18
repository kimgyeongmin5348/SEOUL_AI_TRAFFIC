import { useState, useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import MapPlaceholder from "../components/MapPlaceholder"
import PlaceSearchInput from "../components/PlaceSearchInput"
import { getLiveSeoulRoutes, RouteResult } from "../services/routing"
import { resolvePlace, reverseGeocodeCurrentLocation } from "../services/placeSearch"
import {
  fetchFavoriteRoutes,
  fetchNearbyParking,
  recordRouteSearch,
  FavoriteRouteItem,
  ParkingLotItem,
} from "../services/api"
import { useAuth } from "../auth"
import type { PlaceSuggestion } from "../types/place"

const trafficColor = { green: "#34c759", yellow: "#ff9500", red: "#ff3b30" }

const POPULAR_ROUTES = [
  { from: "마포구 합정동", to: "강남구 역삼동", label: "합정 ➔ 역삼" },
  { from: "영등포구 여의도동", to: "종로구 광화문", label: "여의도 ➔ 광화문" },
  { from: "송파구 잠실동", to: "마포구 홍대입구", label: "잠실 ➔ 홍대" },
  { from: "구로구 신도림동", to: "강남구 테헤란로", label: "신도림 ➔ 강남" },
  { from: "노원구 상계동", to: "서초구 양재동", label: "노원 ➔ 양재" },
]

function explanationSentences(text: string | null | undefined) {
  if (!text) return []
  const cleaned = text
    .replace(/\*\*/g, "")
    .replace(/^\s*(?:추천 이유|AI 추천 근거)\s*[:：]\s*/i, "")
    .replace(/\s+/g, " ")
    .trim()
  return (cleaned.match(/[^.!?]+[.!?]?/g) || [cleaned])
    .map((sentence) => sentence.trim())
    .filter(Boolean)
}

function shortExplanation(text: string | null | undefined) {
  const sentence = explanationSentences(text)[0]
  if (!sentence) return ""
  return sentence.length > 86 ? `${sentence.slice(0, 83).trim()}…` : sentence
}

export default function Route() {
  const [searchParams] = useSearchParams()
  const { user } = useAuth()
  const initialOrigin = searchParams.get("origin") || ""
  const initialDest = searchParams.get("dest") || ""
  const departureAt = searchParams.get("departure") || undefined
  const [originPlace, setOriginPlace] = useState<PlaceSuggestion | null>(null)
  const [destPlace, setDestPlace] = useState<PlaceSuggestion | null>(null)

  const [origin, setOrigin] = useState(initialOrigin)
  const [dest, setDest] = useState(initialDest)
  const [selected, setSelected] = useState("A")
  const [routeList, setRouteList] = useState<RouteResult[]>([])
  const [originPoint, setOriginPoint] = useState<{ name: string; lat: number; lng: number } | null>(null)
  const [destPoint, setDestPoint] = useState<{ name: string; lat: number; lng: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [locating, setLocating] = useState(false)
  const [locationMessage, setLocationMessage] = useState("")
  const [error, setError] = useState("")
  const [predictionMessage, setPredictionMessage] = useState("")
  const [parkingLots, setParkingLots] = useState<ParkingLotItem[]>([])
  const [parkingMessage, setParkingMessage] = useState("")
  const [selectedParkingCode, setSelectedParkingCode] = useState<string | null>(null)
  const [isParkingCollapsed, setIsParkingCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [isDetailsOpen, setIsDetailsOpen] = useState(true)
  const requestId = useRef(0)
  const locationId = useRef(0)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener("resize", checkMobile)
    return () => {
      window.removeEventListener("resize", checkMobile)
      requestId.current++
      locationId.current++
    }
  }, [])

  const useCurrentLocation = () => {
    if (!window.isSecureContext || !navigator.geolocation) {
      setLocationMessage("위치 기능은 HTTPS 또는 localhost의 지원 브라우저에서 사용할 수 있습니다.")
      return
    }
    const id = ++locationId.current
    setLocating(true)
    setLocationMessage("현재 위치를 확인하고 있습니다…")
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      if (id !== locationId.current) return
      try {
        setLocationMessage("도로명 주소를 확인하고 있습니다…")
        const currentPlace = await reverseGeocodeCurrentLocation(coords.latitude, coords.longitude)
        if (id !== locationId.current) return
        const displayAddress = currentPlace.roadAddress || currentPlace.address || currentPlace.name
        setOrigin(displayAddress)
        setOriginPlace(currentPlace)
        setLocationMessage(`${displayAddress} · 정확도 약 ${Math.round(coords.accuracy)}m`)
      } catch (err) {
        if (id !== locationId.current) return
        setOriginPlace(null)
        setLocationMessage(err instanceof Error && err.message === "OUTSIDE_SEOUL"
          ? "현 위치가 서울이 아닙니다. 현위치로부터 경로설정을 사용하지 못합니다."
          : "현재 위치의 도로명 주소를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.")
      } finally {
        if (id === locationId.current) setLocating(false)
      }
    }, (failure) => {
      if (id !== locationId.current) return
      setLocating(false)
      setLocationMessage(failure.code === 1
        ? "위치 권한이 거부되었습니다. 브라우저 사이트 설정에서 위치 접근을 허용한 뒤 다시 시도해 주세요."
        : failure.code === 3
          ? "위치 확인 시간이 초과되었습니다. 다시 시도하거나 출발지를 직접 입력해 주세요."
          : "현재 위치를 확인할 수 없습니다. 기기의 위치 서비스를 켜거나 출발지를 직접 입력해 주세요.")
    }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60_000 })
  }

  const [dbFavorites, setDbFavorites] = useState<FavoriteRouteItem[]>([])

  useEffect(() => {
    if (!user) { setDbFavorites([]); return }
    fetchFavoriteRoutes().then((res) => {
      if (res.routes && res.routes.length > 0) {
        setDbFavorites(res.routes)
      }
    })
  }, [user])

  const runAnalysis = async (startPlace: PlaceSuggestion, endPlace: PlaceSuggestion) => {
    const id = ++requestId.current
    setLoading(true)
    setError("")
    setPredictionMessage("")
    setParkingLots([])
    setParkingMessage("주변 주차장을 확인하고 있습니다…")
    setSelectedParkingCode(null)
    setRouteList([])
    setOriginPoint(null)
    setDestPoint(null)
    if (user && startPlace.source !== "current" && endPlace.source !== "current") {
      void recordRouteSearch(startPlace.name, endPlace.name).catch(() => {})
    }
    try {
      const parkingRequest = fetchNearbyParking(endPlace.lat, endPlace.lng)
        .then((lots) => ({ lots, error: "" }))
        .catch((parkingError) => ({
          lots: [] as ParkingLotItem[],
          error: parkingError instanceof Error ? parkingError.message : "주변 주차장을 불러오지 못했습니다.",
        }))
      const res = await getLiveSeoulRoutes(startPlace, endPlace, departureAt)
      if (id !== requestId.current) return
      setPredictionMessage(res.predictionMessage)
      setRouteList(res.routes)
      setOriginPoint(res.origin)
      setDestPoint(res.dest)
      const best = res.routes.find((r) => r.ai) || res.routes[0]
      if (best) {
        setSelected(best.id)
      }
      const parking = await parkingRequest
      if (id !== requestId.current) return
      setParkingLots(parking.lots)
      setParkingMessage(
        parking.error || (parking.lots.length ? "" : "반경 1.5km 안에 위치가 확인된 일반 주차장이 없습니다."),
      )
    } catch (err) {
      if (id === requestId.current) setError(err instanceof Error ? err.message : "경로 계산에 실패했습니다. 다시 시도해 주세요.")
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }

  const runTextAnalysis = async (startText: string, endText: string) => {
    if (!startText.trim() || !endText.trim()) return
    const id = ++requestId.current
    setLoading(true)
    setError("")
    setPredictionMessage("")
    try {
      const [startPlace, endPlace] = await Promise.all([
        resolvePlace(startText),
        resolvePlace(endText),
      ])
      if (id !== requestId.current) return
      setOrigin(startPlace.name)
      setDest(endPlace.name)
      setOriginPlace(startPlace)
      setDestPlace(endPlace)
      await runAnalysis(startPlace, endPlace)
    } catch (err) {
      if (id === requestId.current) {
        setError(err instanceof Error ? err.message : "장소를 찾지 못했습니다.")
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    const qOrigin = searchParams.get("origin")
    const qDest = searchParams.get("dest")
    if (qOrigin && qDest) {
      setOrigin(qOrigin)
      setDest(qDest)
      setOriginPlace(null)
      setDestPlace(null)
      void runTextAnalysis(qOrigin, qDest)
    } else {
      requestId.current++
      setOrigin(qOrigin || "")
      setDest(qDest || "")
      setOriginPlace(null)
      setDestPlace(null)
      setRouteList([])
      setOriginPoint(null)
      setDestPoint(null)
      setPredictionMessage("")
      setParkingLots([])
      setParkingMessage("")
      setSelectedParkingCode(null)
      setError("")
    }
  }, [searchParams])

  const selectedRoute = routeList.find((r) => r.id === selected) || routeList[0]
  const aiRecommendedRoute = routeList.find((route) => route.ai) || routeList[0]
  const hasResults = routeList.length > 0
  const aiExplanation = explanationSentences(aiRecommendedRoute?.reason).slice(0, 3)
  const recommendationMeta = predictionMessage.split(" · ").slice(0, 2).join(" · ")

  return (
    <div className="min-h-full flex relative" style={{ minHeight: "100dvh" }}>
      <SubpageBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 md:pl-28 md:pr-8 px-3 sm:px-6 pb-24 md:pb-8 pt-[max(64px,calc(env(safe-area-inset-top)+56px))] md:pt-6 max-w-7xl mx-auto w-full">
        <div className="pt-2 md:pt-4 pb-3">
          <div className="animate-slide-up">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1.5">
              <h1
                className="text-white text-xl sm:text-2xl font-bold tracking-tight"
                style={{
                  fontFamily: "var(--font-display)",
                  textShadow: "0 2px 12px rgba(0,0,0,0.35)",
                }}
              >
                서울 전역 도로망 경로 분석
              </h1>
              <span
                className="self-start sm:self-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{
                  background: "rgba(0,122,255,0.2)",
                  color: "#60a5fa",
                  border: "1px solid rgba(96,165,250,0.3)",
                  fontFamily: "var(--font-body)",
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#60a5fa] pulse-dot" />
                베스트 학습 모델 경로 추천
              </span>
            </div>
            <p
              className="text-white/70 text-xs sm:text-sm mb-3"
              style={{ fontFamily: "var(--font-body)" }}
            >
              실제 도로 경로 · 실시간 도로 속도 및 AI 교통량·돌발상황 통합 소요시간 산출
              {departureAt && ` · 출발 ${new Date(departureAt).toLocaleString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`}
            </p>
          </div>

          {/* Search Box (Mobile Stacked / Desktop Single-Row) */}
          <div className="glass p-3.5 sm:p-4 mb-4 animate-slide-up-delay-1" style={{ borderRadius: 20 }}>
            {/* Mobile Layout (< 640px) */}
            <div className="flex flex-col gap-2.5 sm:hidden">
              <PlaceSearchInput
                label="출발지"
                value={origin}
                placeholder="출발지: 강남역, 서울시청, 테헤란로 123"
                selectedPlace={originPlace}
                onValueChange={(value) => {
                  locationId.current++
                  setLocating(false)
                  setLocationMessage("")
                  setOrigin(value)
                  setOriginPlace(null)
                }}
                onSelect={(place) => {
                  setOrigin(place.name)
                  setOriginPlace(place)
                  setLocationMessage(`${place.name} · ${place.roadAddress || place.address}`)
                }}
                onSubmit={() => {
                  if (originPlace && destPlace) void runAnalysis(originPlace, destPlace)
                }}
              />

              {/* Quick actions for mobile: Location & Swap */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={useCurrentLocation}
                  disabled={locating || loading}
                  className="py-2.5 px-3 rounded-xl bg-white/90 hover:bg-white text-xs font-semibold text-[#007aff] border border-black/5 shadow-2xs flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  <span>◎</span>
                  <span>{locating ? "위치 확인 중…" : "현 위치로 설정"}</span>
                </button>

                <button
                  type="button"
                  disabled={locating}
                  onClick={() => {
                    const previousOrigin = origin
                    const previousOriginPlace = originPlace
                    setOrigin(dest)
                    setOriginPlace(destPlace)
                    setDest(previousOrigin)
                    setDestPlace(previousOriginPlace)
                    if (destPlace && previousOriginPlace) {
                      void runAnalysis(destPlace, previousOriginPlace)
                    }
                  }}
                  className="py-2.5 px-3 rounded-xl bg-white/90 hover:bg-white text-xs font-semibold text-[#4a4a68] border border-black/5 shadow-2xs flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <span>⇅</span>
                  <span>출발·도착 맞바꾸기</span>
                </button>
              </div>

              <PlaceSearchInput
                label="도착지"
                value={dest}
                placeholder="도착지: 잠실역, 광화문, 세종대로 110"
                selectedPlace={destPlace}
                onValueChange={(value) => {
                  setDest(value)
                  setDestPlace(null)
                }}
                onSelect={(place) => {
                  setDest(place.name)
                  setDestPlace(place)
                }}
                onSubmit={() => {
                  if (originPlace && destPlace) void runAnalysis(originPlace, destPlace)
                }}
              />

              <button
                type="button"
                onClick={() => {
                  if (!originPlace || !destPlace) {
                    setError("검색 결과에서 출발지와 도착지를 선택해 주세요.")
                    return
                  }
                  void runAnalysis(originPlace, destPlace)
                }}
                disabled={loading || locating || !originPlace || !destPlace}
                className="w-full py-3.5 px-4 font-semibold text-white text-sm rounded-xl transition-all shadow-md active:scale-98 disabled:opacity-50 flex items-center justify-center gap-2"
                style={{
                  background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                  fontFamily: "var(--font-display)",
                }}
              >
                {loading ? "경로 계산 중…" : "AI 경로 분석 시작"}
              </button>
            </div>

            {/* Desktop Layout (>= 640px) */}
            <div className="hidden sm:flex flex-row gap-2 items-center">
              <PlaceSearchInput
                label="출발지"
                value={origin}
                placeholder="출발지 검색: 강남역, 서울시청, 테헤란로 123"
                selectedPlace={originPlace}
                onValueChange={(value) => {
                  locationId.current++
                  setLocating(false)
                  setLocationMessage("")
                  setOrigin(value)
                  setOriginPlace(null)
                }}
                onSelect={(place) => {
                  setOrigin(place.name)
                  setOriginPlace(place)
                  setLocationMessage(`${place.name} · ${place.roadAddress || place.address}`)
                }}
                onSubmit={() => {
                  if (originPlace && destPlace) void runAnalysis(originPlace, destPlace)
                }}
              />

              <button
                type="button"
                onClick={useCurrentLocation}
                disabled={locating || loading}
                className="px-3 py-3 rounded-xl bg-white text-sm text-[#007aff] whitespace-nowrap disabled:opacity-50 shadow-2xs hover:bg-gray-50 border border-black/5"
              >
                {locating ? "위치 확인 중…" : "◎ 현 위치"}
              </button>

              <button
                disabled={locating}
                onClick={() => {
                  const previousOrigin = origin
                  const previousOriginPlace = originPlace
                  setOrigin(dest)
                  setOriginPlace(destPlace)
                  setDest(previousOrigin)
                  setDestPlace(previousOriginPlace)
                  if (destPlace && previousOriginPlace) {
                    void runAnalysis(destPlace, previousOriginPlace)
                  }
                }}
                className="p-3 rounded-xl hover:bg-white/70 transition-all border border-black/5 text-[#007aff] cursor-pointer shadow-2xs bg-white"
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

              <PlaceSearchInput
                label="도착지"
                value={dest}
                placeholder="도착지 검색: 잠실역, 광화문, 세종대로 110"
                selectedPlace={destPlace}
                onValueChange={(value) => {
                  setDest(value)
                  setDestPlace(null)
                }}
                onSelect={(place) => {
                  setDest(place.name)
                  setDestPlace(place)
                }}
                onSubmit={() => {
                  if (originPlace && destPlace) void runAnalysis(originPlace, destPlace)
                }}
              />

              <button
                onClick={() => {
                  if (!originPlace || !destPlace) {
                    setError("검색 결과에서 출발지와 도착지를 선택해 주세요.")
                    return
                  }
                  void runAnalysis(originPlace, destPlace)
                }}
                disabled={loading || locating || !originPlace || !destPlace}
                className="px-6 py-3 font-semibold text-white text-sm whitespace-nowrap cursor-pointer hover:opacity-90 transition-opacity shadow-md disabled:opacity-50"
                style={{
                  borderRadius: 14,
                  background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                  fontFamily: "var(--font-display)",
                }}
              >
                {loading ? "경로 계산 중…" : "AI 경로 분석"}
              </button>
            </div>

            {locationMessage && <p role="status" className="mt-2.5 text-xs text-[#6b6b8a]">{locationMessage}</p>}
            {predictionMessage && !hasResults && <p role="status" className="mt-2.5 text-xs sm:text-sm text-[#4a4a68] font-medium">{predictionMessage}</p>}
            {error && <p role="alert" className="mt-2.5 text-xs sm:text-sm text-red-600">{error}</p>}

            {/* 빠른 추천 경로 칩 (가로 스크롤 & no-scrollbar) */}
            <div className="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-black/5 overflow-x-auto no-scrollbar text-xs">
              <span className="text-[#6b6b8a] whitespace-nowrap text-[11px] font-medium shrink-0">
                {dbFavorites.length > 0 ? "🔥 최다 검색:" : "서울 추천:"}
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
                  disabled={locating}
                  onClick={() => {
                    setOrigin(p.from)
                    setDest(p.to)
                    setOriginPlace(null)
                    setDestPlace(null)
                    void runTextAnalysis(p.from, p.to)
                  }}
                  className="px-2.5 py-1 rounded-lg bg-white/70 hover:bg-white text-[#33334d] border border-black/5 transition-all text-[11px] whitespace-nowrap cursor-pointer font-medium shadow-2xs shrink-0"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className={`route-workspace animate-slide-up-delay-2 ${hasResults ? "has-results" : ""}`}>
          {/* Route list */}
          <div className="route-recommendations flex flex-col gap-3">
            {hasResults && aiRecommendedRoute && (
              <section 
                className={`route-ai-brief cursor-pointer transition-all ${selected === aiRecommendedRoute.id ? 'ring-2 ring-[#007aff] shadow-lg' : ''}`}
                onClick={() => setSelected(aiRecommendedRoute.id)}
                aria-live="polite" 
                aria-label="AI 추천 브리핑"
              >
                <div className="route-ai-brief__glow" aria-hidden="true" />
                <div className="route-ai-brief__header">
                  <div>
                    <span className="route-ai-brief__eyebrow">✦ AI ROUTE BRIEF</span>
                    <h2>경로 {aiRecommendedRoute.id}를 추천해요</h2>
                  </div>
                  <span className="route-ai-brief__status">추천 완료</span>
                </div>

                <div className="route-ai-brief__metrics" aria-label="추천 경로 핵심 정보">
                  <div><span>예상 시간</span><strong>{aiRecommendedRoute.time}분</strong></div>
                  <div><span>주행 거리</span><strong>{aiRecommendedRoute.distance}km</strong></div>
                  <div><span>추천 방식</span><strong>AI 추천</strong></div>
                </div>

                <div className="route-ai-brief__reason">
                  <p className="route-ai-brief__reason-label">이 경로를 고른 이유</p>
                  <ol>
                    {(aiExplanation.length > 0
                      ? aiExplanation
                      : [
                          "기본 소요시간과 예측 교통량을 함께 비교해 가장 유리한 후보를 골랐어요.",
                          "도로 상황에 따라 실제 도착 시간은 달라질 수 있어요.",
                        ]
                    ).map((sentence, index) => (
                      <li key={`${index}-${sentence}`}>
                        <span>{index + 1}</span>
                        <p>{sentence}</p>
                      </li>
                    ))}
                  </ol>
                </div>

                <div className="route-ai-brief__footer">
                  <span>주요 경유 · {aiRecommendedRoute.via}</span>
                  {recommendationMeta && <span>{recommendationMeta}</span>}
                </div>
              </section>
            )}
            {routeList.filter(r => !r.ai).map((r) => {
              const isSelected = r.id === selected
              const color = trafficColor[r.trafficLevel]
              return (
                <div
                  key={r.id}
                  onClick={() => setSelected(r.id)}
                  className="glass item-glide cursor-pointer"
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
                          className="w-7 h-7 flex items-center justify-center text-sm font-bold shrink-0"
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
                        <div className="min-w-0">
                          <p
                            className="font-semibold text-[#1a1a2e] truncate"
                            style={{
                              fontFamily: "var(--font-display)",
                              fontSize: 15,
                            }}
                          >
                            {r.label}
                          </p>
                          <p
                            className="text-xs text-[#6b6b8a] truncate"
                            style={{ fontFamily: "var(--font-body)" }}
                          >
                            경유: {r.via}
                          </p>
                        </div>
                      </div>
                      {r.ai && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-semibold text-white shadow-xs shrink-0"
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

                    <div className="flex items-end gap-3 mt-3 flex-wrap">
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
                        <span
                          className="text-[10px] font-semibold ml-1.5 px-1.5 py-0.5 rounded"
                          style={{
                            background: r.ai ? "rgba(94,92,230,0.14)" : "rgba(0,122,255,0.12)",
                            color: r.ai ? "#5e5ce6" : "#007aff",
                          }}
                        >
                          {r.ai ? "실시간 속도·AI 반영" : "실시간 속도 반영"}
                        </span>
                        {r.delayMin > 0 && (
                          <span className="text-[10px] font-semibold text-[#ff3b30] bg-[#ff3b30]/10 px-1.5 py-0.5 rounded ml-1">
                            +{r.delayMin}분 정체
                          </span>
                        )}
                      </div>
                      <div
                        className="text-xs text-[#6b6b8a] pb-1 flex items-center gap-1.5"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        <span>{r.distance}km</span>
                        <span>·</span>
                        <span style={{ color }}>{r.traffic} ({r.avgSpeed}km/h)</span>
                      </div>
                      <div
                        className="ml-auto text-xs px-2.5 py-1 rounded-full font-semibold shrink-0"
                        style={{
                          background: `${color}18`,
                          color,
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        일반 경로
                      </div>
                    </div>

                    {r.reason && (
                      <div
                        className="mt-3 p-3 rounded-xl text-xs leading-relaxed"
                        style={{
                          background: "rgba(94,92,230,0.08)",
                          color: "#3f3f58",
                          border: "1px solid rgba(94,92,230,0.15)",
                          fontFamily: "var(--font-body)",
                        }}
                      >
                        <span className="font-semibold text-[#5e5ce6]">AI 한줄 요약</span>
                        <p className="mt-1 text-[13px] leading-relaxed">{shortExplanation(r.reason)}</p>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Map + detail */}
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            <div
              className="glass flex flex-col min-w-0"
              style={{ borderRadius: 24, overflow: "hidden" }}
            >
              <MapPlaceholder
                height={isMobile ? 320 : 460}
                routeCoordinates={selectedRoute?.coordinates}
                originPoint={originPoint || undefined}
                destPoint={destPoint || undefined}
                parkingLots={parkingLots}
                enableTraffic={false}
                enableIncidents={false}
                enableParking={true}
                selectedParkingLotId={selectedParkingCode}
                onSelectParkingLot={(lot) => setSelectedParkingCode(lot ? lot.parking_code : null)}
              />
            </div>

            {(parkingLots.length > 0 || parkingMessage) && (
              <section className="glass p-4 sm:p-5" style={{ borderRadius: 20 }} aria-label="도착지 주변 주차장">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🅿️</span>
                    <h3 className="text-[#1a1a2e] font-semibold" style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>
                      도착지 주변 주차장 {parkingLots.length > 0 && `(${parkingLots.length}곳)`}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#6b6b8a]">직선거리 반경 1.5km</span>
                    {parkingLots.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setIsParkingCollapsed((prev) => !prev)}
                        className="text-xs font-semibold text-[#007aff] hover:underline px-2.5 py-1 rounded-lg bg-blue-50/80 border border-blue-200/50 cursor-pointer"
                      >
                        {isParkingCollapsed ? "목록 펼치기 ▾" : "목록 접기 ▴"}
                      </button>
                    )}
                  </div>
                </div>

                {parkingMessage && <p role="status" className="text-sm text-[#6b6b8a] mt-1">{parkingMessage}</p>}

                {!isParkingCollapsed && parkingLots.length > 0 && (
                  <div className="grid gap-2.5 sm:grid-cols-2 mt-3">
                    {parkingLots.map((lot) => {
                      const isSelected = selectedParkingCode === lot.parking_code
                      const hasLive = lot.realtime_status === "AVAILABLE" && lot.available_spaces !== null
                      return (
                        <article
                          key={lot.parking_code}
                          onClick={() => setSelectedParkingCode((prev) => (prev === lot.parking_code ? null : lot.parking_code))}
                          className={`rounded-2xl p-3.5 border transition-all cursor-pointer ${
                            isSelected
                              ? "bg-blue-50/80 border-[#007aff] ring-2 ring-[#007aff]/30 shadow-sm"
                              : "bg-white/70 border-black/5 hover:border-[#007aff]/40 hover:bg-white/90"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="font-semibold text-sm text-[#1a1a2e] truncate">{lot.name}</p>
                              <p className="text-xs text-[#6b6b8a] truncate mt-0.5">{lot.address}</p>
                            </div>
                            <div className="flex flex-col items-end shrink-0">
                              <span className="text-xs whitespace-nowrap text-[#007aff] font-semibold">
                                {lot.distance_m < 1000 ? `${lot.distance_m}m` : `${(lot.distance_m / 1000).toFixed(1)}km`}
                              </span>
                              <span className="text-[10px] text-[#007aff]/70 mt-0.5 font-medium">지도로 보기 ↗</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 mt-2.5 text-xs flex-wrap">
                            <span className={`px-2 py-0.5 rounded-lg font-semibold text-[11px] ${
                              hasLive
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                                : "bg-slate-100 text-slate-500"
                            }`}>
                              {hasLive
                                ? `주차 가능 ${lot.available_spaces}대`
                                : "실시간 정보 없음"}
                            </span>
                            <span className="text-[#6b6b8a]">총 {lot.capacity}면 · {lot.paid ? "유료" : "무료/미확인"}</span>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            )}

            {/* Route detail */}
            {selectedRoute && (
              <div className="glass p-4 sm:p-5" style={{ borderRadius: 20 }}>
                <button 
                  onClick={() => setIsDetailsOpen(!isDetailsOpen)}
                  className="w-full flex items-center justify-between mb-3 hover:opacity-80 transition-opacity"
                >
                  <h3
                    className="text-[#1a1a2e]"
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: 16,
                    }}
                  >
                    {selectedRoute?.label} 주행 상세 분석
                  </h3>
                  <span className="text-[#007aff] text-xl leading-none">
                    {isDetailsOpen ? "−" : "+"}
                  </span>
                </button>

                {isDetailsOpen && (
                  <div className="animate-fade-in">
                    {/* 실시간 속도 및 AI 예측 안내 배너 */}
                    <div className="mb-4 p-3.5 rounded-xl bg-blue-50/70 border border-blue-200/60 flex items-start gap-2.5 text-xs text-[#2c3e50] leading-relaxed">
                      <span className="text-base shrink-0 mt-0.5">ℹ️</span>
                      <div>
                        <span className="font-semibold text-[#007aff]">실시간 속도·AI 경로 분석:</span>
                        {" "}본 경로는 OSRM 도로망 기본 시간에 <strong className="text-[#1a1a2e]">서울시 실시간 관측 속도 지연, AI 모델의 미래 혼잡도 예측, 실시간 돌발상황(사고·공사)</strong>을 모두 반영하여 실제 체감 소요시간과 최적 경로를 산출합니다.
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 sm:gap-3">
                      {[
                        {
                          label: "AI 최종 예측 소요 시간",
                          value: selectedRoute?.delayMin > 0
                            ? `${selectedRoute?.time}분 (정체 +${selectedRoute?.delayMin}분)`
                            : `${selectedRoute?.time}분`,
                          color: "#007aff",
                        },
                        {
                          label: "교통 미반영 기본 시간",
                          value: `${selectedRoute?.baseTime}분`,
                          color: "#6b6b8a",
                        },
                        {
                          label: "적용 AI 모델 알고리즘",
                          value: selectedRoute.modelVersion ? selectedRoute.modelVersion.replace('route_', '').split('_')[0].toUpperCase() : "기본 OSRM 모델",
                          color: "#5e5ce6",
                        },
                        {
                          label: "실제 주행 거리 / 평균 속도",
                          value: `${selectedRoute?.distance}km / ${selectedRoute?.avgSpeed}km/h`,
                          color: "#4a4a68",
                        },
                        {
                          label: "도로망 데이터 매칭률",
                          value: selectedRoute.linkMatchRatio !== undefined ? `${Math.round(selectedRoute.linkMatchRatio * 100)}%` : "100%",
                          color: "#007aff",
                        },
                        {
                          label: "경로 내 활성 돌발(사고/공사)",
                          value: selectedRoute.incidents ? `${selectedRoute.incidents}건 발생` : "발견되지 않음",
                          color: selectedRoute.incidents ? "#ff3b30" : "#34c759",
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
                            className="font-semibold text-sm sm:text-base truncate"
                            style={{
                              fontFamily: "var(--font-display)",
                              color: item.color,
                            }}
                          >
                            {item.value}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

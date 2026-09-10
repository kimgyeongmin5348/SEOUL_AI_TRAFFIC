import { useEffect, useRef, useState } from "react"
import precisionRoadsData from "../data/seoul_roads.json"
import { loadKakaoMaps } from "../services/kakaoMaps"
import { resolvePlace } from "../services/placeSearch"

export interface IncidentItem {
  id: number | string
  type: string
  road: string
  location: string
  description?: string
  startTime?: string
  estEnd?: string
  impact?: "high" | "medium" | "low"
}

interface MapProps {
  height?: number | string
  searchQuery?: string
  incidents?: IncidentItem[]
  roadSpeeds?: Array<{ road: string; speed: number; avg: number; level: string }>
  selectedIncidentId?: number | string | null
  onSelectIncident?: (incident: IncidentItem) => void
  routeCoordinates?: [number, number][]
  originPoint?: { name: string; lat: number; lng: number }
  destPoint?: { name: string; lat: number; lng: number }
}

type MapOverlay = kakao.maps.Polyline | kakao.maps.CustomOverlay | kakao.maps.Circle

function getIncidentCoord(inc: IncidentItem): [number, number] {
  const text = `${inc.road} ${inc.location} ${inc.description || ""}`
  if (text.includes("분당수서") || text.includes("탄천1교") || text.includes("청담대교남단")) return [37.5080, 127.0680]
  if (text.includes("도봉T") || text.includes("도봉터널")) return [37.6780, 127.0520]
  if (text.includes("서초터널")) return [37.4650, 127.0180]
  if (text.includes("봉천터널")) return [37.4720, 126.9450]
  if (text.includes("소하IC") || text.includes("소하JC")) return [37.4450, 126.8950]
  if (text.includes("잠실철교") || text.includes("잠실대교")) return [37.5180, 127.0860]
  if (text.includes("은평구청") || text.includes("녹번역") || text.includes("은평로")) return [37.6020, 126.9290]
  if (text.includes("녹사평역") || text.includes("이태원역") || text.includes("이태원로")) return [37.5340, 126.9930]
  if (text.includes("탄천동로") || text.includes("종합운동장")) return [37.5110, 127.0750]
  if (text.includes("봉은교") || text.includes("탄천나들목")) return [37.5140, 127.0680]
  if (text.includes("소공로") || text.includes("서울광장") || text.includes("한국은행")) return [37.5640, 126.9790]
  if (text.includes("솔샘로") || text.includes("삼양입구")) return [37.6250, 127.0200]
  if (text.includes("성산로") || text.includes("마포구청역")) return [37.5630, 126.9030]
  if (text.includes("정동길") || text.includes("정동제일교회")) return [37.5670, 126.9720]
  if (text.includes("정릉터널") || text.includes("정릉램프")) return [37.6040, 126.9940]
  if (text.includes("동일로") || text.includes("도봉운전면허")) return [37.6530, 127.0600]
  if (text.includes("군자교") || text.includes("성동JC")) return [37.5580, 127.0700]
  if (text.includes("다산로") || text.includes("신당역")) return [37.5650, 127.0180]
  if (text.includes("영동대교남단") || text.includes("성수대교남단")) return [37.5290, 127.0500]
  if (text.includes("서강대교북단") || text.includes("양화대교북단")) return [37.5420, 126.9180]
  if (text.includes("방화대교남단") || text.includes("가양대교남단")) return [37.5700, 126.8400]
  if (text.includes("마포대교") || text.includes("양화대교")) return [37.5400, 126.9200]
  if (text.includes("서초IC")) return [37.4860, 127.0250]
  if (text.includes("하남분기점")) return [37.5350, 127.1850]
  if (text.includes("강남대로") || text.includes("양재IC")) return [37.4800, 127.0300]
  if (text.includes("광화문")) return [37.5759, 126.9768]
  if (text.includes("홍지문터널")) return [37.5950, 126.9530]
  return [37.5300, 126.9800]
}

function makePill(text: string, background: string) {
  const element = document.createElement("div")
  element.textContent = text
  Object.assign(element.style, {
    background,
    color: "white",
    padding: "5px 10px",
    borderRadius: "14px",
    border: "2px solid white",
    boxShadow: "0 4px 12px rgba(0,0,0,0.28)",
    fontSize: "11px",
    fontWeight: "700",
    whiteSpace: "nowrap",
    fontFamily: "sans-serif",
  })
  return element
}

export default function MapPlaceholder({
  height = 480,
  searchQuery = "",
  incidents = [],
  roadSpeeds = [],
  selectedIncidentId = null,
  onSelectIncident,
  routeCoordinates,
  originPoint,
  destPoint,
}: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<kakao.maps.Map | null>(null)
  const roadOverlaysRef = useRef<MapOverlay[]>([])
  const routeOverlaysRef = useRef<MapOverlay[]>([])
  const searchOverlayRef = useRef<kakao.maps.CustomOverlay | null>(null)
  const locationOverlaysRef = useRef<MapOverlay[]>([])
  const incidentOverlaysRef = useRef(new Map<string | number, { overlay: kakao.maps.CustomOverlay; lat: number; lng: number }>())
  const currentPosition = useRef<GeolocationCoordinates | null>(null)
  const searchRequestId = useRef(0)
  const [mapReady, setMapReady] = useState(false)
  const [mapError, setMapError] = useState("")
  const [showTrafficLines, setShowTrafficLines] = useState(true)
  const [locationStatus, setLocationStatus] = useState("현재 위치 확인 중…")
  const viewHasContext = Boolean(searchQuery || routeCoordinates?.length || selectedIncidentId != null)

  useEffect(() => {
    let active = true
    let observer: ResizeObserver | null = null
    loadKakaoMaps().then((sdk) => {
      if (!active || !containerRef.current) return
      const map = new sdk.maps.Map(containerRef.current, {
        center: new sdk.maps.LatLng(37.5320, 126.9950),
        level: 8,
      })
      map.addControl(new sdk.maps.MapTypeControl(), sdk.maps.ControlPosition.TOPRIGHT)
      map.addControl(new sdk.maps.ZoomControl(), sdk.maps.ControlPosition.RIGHT)
      mapRef.current = map
      setMapReady(true)
      observer = new ResizeObserver(() => map.relayout())
      observer.observe(containerRef.current)
    }).catch((error) => {
      if (active) setMapError(error instanceof Error ? error.message : "카카오 지도를 불러오지 못했습니다.")
    })
    return () => {
      active = false
      observer?.disconnect()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    if (!window.isSecureContext || !navigator.geolocation) {
      setLocationStatus("현재 위치는 HTTPS 또는 localhost에서 사용할 수 있습니다.")
      return
    }
    let active = true
    let firstFix = true
    const watchId = navigator.geolocation.watchPosition(({ coords }) => {
      if (!active) return
      currentPosition.current = coords
      const position = new kakao.maps.LatLng(coords.latitude, coords.longitude)
      locationOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      const accuracy = new kakao.maps.Circle({
        map, center: position, radius: coords.accuracy,
        strokeWeight: 1, strokeColor: "#007aff", strokeOpacity: 0.5,
        fillColor: "#007aff", fillOpacity: 0.08,
      })
      const dot = document.createElement("div")
      Object.assign(dot.style, {
        width: "16px", height: "16px", borderRadius: "50%", background: "#007aff",
        border: "3px solid white", boxShadow: "0 2px 8px rgba(0,122,255,.5)",
      })
      const marker = new kakao.maps.CustomOverlay({ map, position, content: dot, zIndex: 9 })
      locationOverlaysRef.current = [accuracy, marker]
      setLocationStatus(`내 위치 · 정확도 약 ${Math.round(coords.accuracy)}m`)
      if (firstFix && !viewHasContext) {
        map.setCenter(position)
        map.setLevel(4)
      }
      firstFix = false
    }, (error) => {
      if (!active) return
      setLocationStatus(error.code === 1
        ? "위치 권한이 꺼져 있습니다. 브라우저 설정에서 허용해 주세요."
        : error.code === 3 ? "위치 확인 시간이 초과되었습니다." : "현재 위치를 확인할 수 없습니다.")
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 })
    return () => {
      active = false
      navigator.geolocation.clearWatch(watchId)
      locationOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      locationOverlaysRef.current = []
    }
  }, [mapReady])

  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    roadOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
    roadOverlaysRef.current = []
    incidentOverlaysRef.current.clear()
    if (showTrafficLines) {
      precisionRoadsData.forEach((road) => {
        const match = roadSpeeds.find((speed) => speed.road.includes(road.name) || road.name.includes(speed.road))
        const speed = match?.speed ?? road.defaultSpeed
        const color = speed < 25 ? "#ff3b30" : speed < 50 ? "#ff9500" : "#34c759"
        const path = (road.coordinates as [number, number][]).map(([lat, lng]) => new kakao.maps.LatLng(lat, lng))
        const outline = new kakao.maps.Polyline({ map, path, strokeColor: "#ffffff", strokeWeight: 7, strokeOpacity: 0.88, zIndex: 2 })
        const line = new kakao.maps.Polyline({ map, path, strokeColor: color, strokeWeight: 4, strokeOpacity: 0.92, zIndex: 3 })
        roadOverlaysRef.current.push(outline, line)
      })
    }
    incidents.forEach((incident) => {
      const [lat, lng] = getIncidentCoord(incident)
      const position = new kakao.maps.LatLng(lat, lng)
      const isAccident = incident.type === "사고"
      const isConstruction = incident.type === "공사"
      const color = isAccident ? "#ff3b30" : isConstruction ? "#ff9500" : "#5e5ce6"
      const symbol = isAccident ? "🚨" : isConstruction ? "🚧" : "🚗"
      const button = makePill(symbol, color)
      button.title = `[${incident.type}] ${incident.road} - ${incident.location}`
      button.style.cursor = "pointer"
      button.addEventListener("click", () => onSelectIncident?.(incident))
      const overlay = new kakao.maps.CustomOverlay({ map, position, content: button, clickable: true, zIndex: 8 })
      roadOverlaysRef.current.push(overlay)
      incidentOverlaysRef.current.set(incident.id, { overlay, lat, lng })
    })
    return () => {
      roadOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      roadOverlaysRef.current = []
      incidentOverlaysRef.current.clear()
    }
  }, [incidents, mapReady, onSelectIncident, roadSpeeds, showTrafficLines])

  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    routeOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
    routeOverlaysRef.current = []
    if (!routeCoordinates || routeCoordinates.length < 2) return
    const path = routeCoordinates.map(([lat, lng]) => new kakao.maps.LatLng(lat, lng))
    const outline = new kakao.maps.Polyline({ map, path, strokeColor: "#ffffff", strokeWeight: 9, strokeOpacity: 0.95, zIndex: 5 })
    const route = new kakao.maps.Polyline({ map, path, strokeColor: "#007aff", strokeWeight: 5, strokeOpacity: 0.95, zIndex: 6 })
    routeOverlaysRef.current.push(outline, route)
    if (originPoint) {
      routeOverlaysRef.current.push(new kakao.maps.CustomOverlay({
        map, position: new kakao.maps.LatLng(originPoint.lat, originPoint.lng),
        content: makePill(`출발: ${originPoint.name}`, "#34c759"), yAnchor: 1.2, zIndex: 10,
      }))
    }
    if (destPoint) {
      routeOverlaysRef.current.push(new kakao.maps.CustomOverlay({
        map, position: new kakao.maps.LatLng(destPoint.lat, destPoint.lng),
        content: makePill(`도착: ${destPoint.name}`, "#ff3b30"), yAnchor: 1.2, zIndex: 10,
      }))
    }
    const bounds = new kakao.maps.LatLngBounds()
    path.forEach((point) => bounds.extend(point))
    map.setBounds(bounds, 55, 55, 55, 55)
    return () => {
      routeOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      routeOverlaysRef.current = []
    }
  }, [destPoint, mapReady, originPoint, routeCoordinates])

  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map || selectedIncidentId == null) return
    const selected = incidentOverlaysRef.current.get(selectedIncidentId)
    if (!selected) return
    map.panTo(new kakao.maps.LatLng(selected.lat, selected.lng))
    map.setLevel(4)
  }, [mapReady, selectedIncidentId])

  useEffect(() => {
    const map = mapRef.current
    const query = searchQuery.trim()
    if (!mapReady || !map || !query) {
      searchOverlayRef.current?.setMap(null)
      searchOverlayRef.current = null
      return
    }
    const id = ++searchRequestId.current
    const timer = window.setTimeout(() => {
      resolvePlace(query).then((place) => {
        if (id !== searchRequestId.current || !mapRef.current) return
        searchOverlayRef.current?.setMap(null)
        const position = new kakao.maps.LatLng(place.lat, place.lng)
        searchOverlayRef.current = new kakao.maps.CustomOverlay({
          map: mapRef.current, position, content: makePill(`📍 ${place.name}`, "#007aff"), yAnchor: 1.2, zIndex: 10,
        })
        mapRef.current.panTo(position)
        mapRef.current.setLevel(4)
      }).catch(() => {})
    }, 300)
    return () => window.clearTimeout(timer)
  }, [mapReady, searchQuery])

  const focusCurrentLocation = () => {
    const coords = currentPosition.current
    if (!coords || !mapRef.current) {
      setLocationStatus("현재 위치를 확인하고 있습니다…")
      return
    }
    mapRef.current.panTo(new kakao.maps.LatLng(coords.latitude, coords.longitude))
    mapRef.current.setLevel(4)
  }

  const handleReset = () => {
    if (!mapRef.current) return
    mapRef.current.setCenter(new kakao.maps.LatLng(37.5320, 126.9950))
    mapRef.current.setLevel(8)
  }

  return (
    <div className="relative overflow-hidden w-full min-w-0 flex-1" style={{ minHeight: height, isolation: "isolate" }}>
      <div ref={containerRef} className="absolute inset-0" style={{ zIndex: 1 }} />
      {mapError && (
        <div role="alert" className="absolute inset-0 z-20 flex items-center justify-center bg-white/90 px-6 text-center text-sm text-red-600">
          {mapError}<br />카카오 JavaScript 키와 등록 도메인을 확인해 주세요.
        </div>
      )}
      <button type="button" className="glass absolute top-3 left-3 z-10 px-3 py-1.5 text-xs font-semibold text-[#007aff] shadow-sm" style={{ borderRadius: 12 }} onClick={handleReset}>
        ◎ 서울 전체 보기
      </button>
      <div className="absolute left-3 right-14 top-14 z-10 flex items-start gap-2 pointer-events-none">
        <button type="button" onClick={focusCurrentLocation} className="glass shrink-0 px-3 py-2 rounded-xl text-xs font-semibold text-[#007aff] pointer-events-auto">◎ 내 위치</button>
        <span role="status" className="glass px-2 py-1.5 rounded-lg text-[11px] text-[#4a4a68] max-w-72">{locationStatus}</span>
      </div>
      <div className="absolute top-3 right-24 z-10">
        <button type="button" onClick={() => setShowTrafficLines((value) => !value)} className="glass px-3 py-1.5 text-xs font-semibold rounded-xl shadow-sm flex items-center gap-1.5" style={{ color: showTrafficLines ? "#007aff" : "#6b6b8a" }}>
          <span className={`w-2 h-2 rounded-full ${showTrafficLines ? "bg-[#007aff]" : "bg-gray-400"}`} />
          <span className="hidden sm:inline">실시간 </span>혼잡도 {showTrafficLines ? "ON" : "OFF"}
        </button>
      </div>
      <div className="glass absolute bottom-3 left-3 right-3 sm:right-auto z-10 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 shadow-sm" style={{ borderRadius: 12 }}>
        {[
          { color: "#34c759", label: "원활 (≥50km/h)" },
          { color: "#ff9500", label: "서행 (25~49km/h)" },
          { color: "#ff3b30", label: "혼잡 (<25km/h)" },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div className="w-3 h-1.5 rounded-full" style={{ background: item.color }} />
            <span className="text-[11px] font-semibold text-[#4a4a68]">{item.label}</span>
          </div>
        ))}
        <div className="w-px h-3 bg-black/10 mx-1" />
        <span className="text-[11px] text-[#ff3b30] font-semibold">🚨 사고</span>
        <span className="text-[11px] text-[#ff9500] font-semibold">🚧 공사</span>
      </div>
    </div>
  )
}

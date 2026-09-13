import { useEffect, useRef, useState } from "react"
import precisionRoadsData from "../data/seoul_roads.json"
import seoulBoundaryData from "../data/seoulBoundary.json"
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
  lat?: number
  lng?: number
  tmX?: number | null
  tmY?: number | null
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

type MapOverlay = kakao.maps.Polyline | kakao.maps.CustomOverlay | kakao.maps.Circle | kakao.maps.Polygon

function makePill(text: string, background: string) {
  const element = document.createElement("div")
  element.textContent = text
  Object.assign(element.style, {
    background,
    color: "white",
    padding: "3px 6px",
    borderRadius: "10px",
    border: "1.5px solid white",
    boxShadow: "0 3px 9px rgba(0,0,0,0.22)",
    fontSize: "9px",
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
  const boundaryOverlaysRef = useRef<kakao.maps.Polygon[]>([])
  const routeOverlaysRef = useRef<MapOverlay[]>([])
  const searchOverlayRef = useRef<kakao.maps.CustomOverlay | null>(null)
  const locationOverlaysRef = useRef<MapOverlay[]>([])
  const incidentOverlaysRef = useRef(new Map<string | number, { overlay: kakao.maps.CustomOverlay; lat: number; lng: number }>())
  const currentPosition = useRef<GeolocationCoordinates | null>(null)
  const searchRequestId = useRef(0)
  const [mapReady, setMapReady] = useState(false)
  const [mapError, setMapError] = useState("")
  const [showTrafficLines, setShowTrafficLines] = useState(true)
  const [showIncidents, setShowIncidents] = useState(true)
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
      const coordinates = seoulBoundaryData.features[0].geometry.coordinates as number[][][][]
      boundaryOverlaysRef.current = coordinates.map((polygon) => new sdk.maps.Polygon({
        map,
        path: polygon.map((ring) => ring.map(([lng, lat]) => new sdk.maps.LatLng(lat, lng))),
        strokeWeight: 3,
        strokeColor: "#5e5ce6",
        strokeOpacity: 0.82,
        strokeStyle: "solid",
        fillColor: "#5e5ce6",
        fillOpacity: 0.025,
        zIndex: 1,
      }))
      setMapReady(true)
      observer = new ResizeObserver(() => map.relayout())
      observer.observe(containerRef.current)
    }).catch((error) => {
      if (active) setMapError(error instanceof Error ? error.message : "카카오 지도를 불러오지 못했습니다.")
    })
    return () => {
      active = false
      observer?.disconnect()
      boundaryOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      boundaryOverlaysRef.current = []
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
    let active = true
    const drawIncident = (incident: IncidentItem, lat: number, lng: number) => {
      if (!active || !showIncidents) return
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
    }
    if (showIncidents) {
      const geocoder = new kakao.maps.services.Geocoder()
      incidents.forEach((incident) => {
        if (typeof incident.lat === "number" && typeof incident.lng === "number") {
          drawIncident(incident, incident.lat, incident.lng)
        } else if (typeof incident.tmX === "number" && typeof incident.tmY === "number") {
          geocoder.transCoord(incident.tmX, incident.tmY, (results, status) => {
            if (status === kakao.maps.services.Status.OK && results[0]) {
              drawIncident(incident, Number(results[0].y), Number(results[0].x))
            }
          }, {
            input_coord: kakao.maps.services.Coords.WTM,
            output_coord: kakao.maps.services.Coords.WGS84,
          })
        }
      })
    }
    return () => {
      active = false
      roadOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      roadOverlaysRef.current = []
      incidentOverlaysRef.current.clear()
    }
  }, [incidents, mapReady, onSelectIncident, roadSpeeds, showIncidents, showTrafficLines])

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
      <div className="absolute top-3 right-24 z-10 flex flex-col items-end gap-2">
        <button type="button" aria-pressed={showTrafficLines} onClick={() => setShowTrafficLines((value) => !value)} className="glass interactive-control px-3 py-1.5 text-xs font-semibold rounded-xl shadow-sm flex items-center gap-1.5" style={{ color: showTrafficLines ? "#007aff" : "#6b6b8a" }}>
          <span className={`switch-track ${showTrafficLines ? "is-on" : ""}`}><span className="switch-thumb" /></span>
          <span className="hidden sm:inline">실시간 </span>혼잡도 {showTrafficLines ? "ON" : "OFF"}
        </button>
        <button type="button" aria-pressed={showIncidents} onClick={() => setShowIncidents((value) => !value)} className="glass interactive-control px-3 py-1.5 text-xs font-semibold rounded-xl shadow-sm flex items-center gap-1.5" style={{ color: showIncidents ? "#ff3b30" : "#6b6b8a" }}>
          <span className={`switch-track incident-switch ${showIncidents ? "is-on" : ""}`}><span className="switch-thumb" /></span>
          돌발상황 {showIncidents ? "ON" : "OFF"}
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

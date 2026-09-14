import { useEffect, useRef, useState } from "react"
import precisionRoadsData from "../data/seoul_roads.json"
import seoulBoundaryData from "../data/seoulBoundary.json"
import { loadKakaoMaps } from "../services/kakaoMaps"
import { resolvePlace } from "../services/placeSearch"
import { fetchNearbyParking, type ParkingLotItem } from "../services/api"

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
  parkingLots?: ParkingLotItem[]
  selectedParkingLotId?: string | null
  onSelectParkingLot?: (lot: ParkingLotItem) => void
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
  parkingLots = [],
  selectedParkingLotId = null,
  onSelectParkingLot,
}: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<kakao.maps.Map | null>(null)
  const roadOverlaysRef = useRef<MapOverlay[]>([])
  const boundaryOverlaysRef = useRef<kakao.maps.Polygon[]>([])
  const routeOverlaysRef = useRef<MapOverlay[]>([])
  const searchOverlayRef = useRef<kakao.maps.CustomOverlay | null>(null)
  const locationOverlaysRef = useRef<MapOverlay[]>([])
  const incidentOverlaysRef = useRef(new Map<string, { overlay: kakao.maps.CustomOverlay; lat: number; lng: number }>())
  const parkingOverlaysRef = useRef<kakao.maps.CustomOverlay[]>([])
  const selectedMarkerOverlayRef = useRef<kakao.maps.CustomOverlay | null>(null)
  const flyAnimationTimersRef = useRef<number[]>([])
  const currentPosition = useRef<GeolocationCoordinates | null>(null)
  const searchRequestId = useRef(0)
  const [mapReady, setMapReady] = useState(false)
  const [mapError, setMapError] = useState("")
  const [showTrafficLines, setShowTrafficLines] = useState(true)
  const [showIncidents, setShowIncidents] = useState(true)
  const [showParking, setShowParking] = useState(true)
  const [internalParkingLots, setInternalParkingLots] = useState<ParkingLotItem[]>([])
  const [locationStatus, setLocationStatus] = useState("현재 위치 확인 중…")
  const effectiveParkingLots = parkingLots && parkingLots.length > 0 ? parkingLots : internalParkingLots
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
      incidentOverlaysRef.current.set(String(incident.id), { overlay, lat, lng })
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

  // 선택된 돌발상황 위치로 부드러운 애니메이션 panTo 이동 및 펄스 하이라이트
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return

    selectedMarkerOverlayRef.current?.setMap(null)
    selectedMarkerOverlayRef.current = null

    if (selectedIncidentId == null) return

    const clearFlyTimers = () => {
      flyAnimationTimersRef.current.forEach((t) => window.clearTimeout(t))
      flyAnimationTimersRef.current = []
    }

    const moveToPosition = (lat: number, lng: number, incident?: IncidentItem) => {
      clearFlyTimers()
      const position = new kakao.maps.LatLng(lat, lng)
      const curLevel = map.getLevel()
      const needsZoomOut = curLevel <= 5

      // 1단계: 멀어지기 (Zoom-out) - 기존 화면이 확대되어 있으면 레벨 7로 시야를 넓혀 전체 조망
      if (needsZoomOut) {
        map.setLevel(7, { animate: true })
      }

      // 2단계: 목표 지점으로 비행 이동 (Pan-to) - 줌아웃 효과 시작 직후 부드럽게 목표 지점으로 이동
      const panDelay = needsZoomOut ? 220 : 0
      const t1 = window.setTimeout(() => {
        if (mapRef.current) {
          mapRef.current.panTo(position)
        }
      }, panDelay)
      flyAnimationTimersRef.current.push(t1)

      // 3단계: 가까워지기 (Zoom-in) - 목표 지점 상공에 도달하면서 상세 레벨(4)로 깊숙이 다이빙
      const zoomInDelay = panDelay + 550
      const t2 = window.setTimeout(() => {
        if (mapRef.current) {
          mapRef.current.setLevel(4, { animate: true })
        }
      }, zoomInDelay)
      flyAnimationTimersRef.current.push(t2)

      // 선택된 돌발상황 위치에 반짝이는 펄스 링 하이라이트 오버레이
      const pulseEl = document.createElement("div")
      pulseEl.style.cssText = "position: relative; display: flex; align-items: center; justify-content: center; pointer-events: none;"
      pulseEl.innerHTML = `
        <div style="position: absolute; width: 50px; height: 50px; border-radius: 50%; background: rgba(255, 59, 48, 0.35); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
        <div style="position: absolute; width: 32px; height: 32px; border-radius: 50%; background: rgba(255, 59, 48, 0.6); border: 2.5px solid white; box-shadow: 0 3px 10px rgba(0,0,0,0.35);"></div>
        <div style="position: relative; z-index: 2; font-size: 16px; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));">${incident?.type === "사고" ? "🚨" : incident?.type === "공사" ? "🚧" : "⚠️"}</div>
      `
      const highlight = new kakao.maps.CustomOverlay({
        map,
        position,
        content: pulseEl,
        zIndex: 15,
      })
      selectedMarkerOverlayRef.current = highlight
    }

    const key = String(selectedIncidentId)
    const cached = incidentOverlaysRef.current.get(key)
    const targetInc = incidents.find((i) => String(i.id) === key)

    if (cached) {
      moveToPosition(cached.lat, cached.lng, targetInc)
    } else if (targetInc) {
      if (typeof targetInc.lat === "number" && typeof targetInc.lng === "number") {
        moveToPosition(targetInc.lat, targetInc.lng, targetInc)
      } else if (typeof targetInc.tmX === "number" && typeof targetInc.tmY === "number") {
        const geocoder = new kakao.maps.services.Geocoder()
        geocoder.transCoord(
          targetInc.tmX,
          targetInc.tmY,
          (results, status) => {
            if (status === kakao.maps.services.Status.OK && results[0]) {
              moveToPosition(Number(results[0].y), Number(results[0].x), targetInc)
            }
          },
          {
            input_coord: kakao.maps.services.Coords.WTM,
            output_coord: kakao.maps.services.Coords.WGS84,
          }
        )
      }
    }

    return () => {
      clearFlyTimers()
    }
  }, [mapReady, selectedIncidentId, incidents])

  // 주차장 토글 시 데이터가 없으면 현재 중심 좌표 기준 주차장 조회
  useEffect(() => {
    if (showParking && (!parkingLots || parkingLots.length === 0) && internalParkingLots.length === 0 && mapReady) {
      const center = mapRef.current?.getCenter()
      const lat = center ? center.getLat() : 37.5665
      const lng = center ? center.getLng() : 126.9780
      fetchNearbyParking(lat, lng, 3500, 15)
        .then((lots) => setInternalParkingLots(lots))
        .catch((err) => console.warn("Failed to fetch nearby parking:", err))
    }
  }, [showParking, parkingLots, internalParkingLots.length, mapReady])

  // 주차장 마커 렌더링
  useEffect(() => {
    const map = mapRef.current
    parkingOverlaysRef.current.forEach((o) => o.setMap(null))
    parkingOverlaysRef.current = []

    if (!mapReady || !map || !showParking || !effectiveParkingLots.length) return

    effectiveParkingLots.forEach((lot) => {
      const position = new kakao.maps.LatLng(lot.latitude, lot.longitude)
      const hasLive = lot.realtime_status === "AVAILABLE" && lot.available_spaces !== null
      const isSelected = selectedParkingLotId === lot.parking_code

      const button = document.createElement("button")
      button.type = "button"
      button.className = "group relative flex items-center transition-transform hover:scale-110 active:scale-95"
      button.style.cursor = "pointer"
      button.setAttribute("aria-label", `${lot.name} 주차장`)

      const badge = document.createElement("div")
      badge.className = `flex items-center gap-1 px-2 py-1 rounded-xl font-bold shadow-md border ${
        isSelected
          ? "bg-[#007aff] text-white border-white scale-110 z-10 ring-2 ring-[#007aff]"
          : hasLive
            ? "bg-emerald-600 text-white border-white/90"
            : "bg-[#2c3e50] text-white border-white/80"
      }`
      badge.style.fontSize = "11px"
      badge.innerHTML = `<span>🅿️</span><span>${hasLive ? `${lot.available_spaces}대` : lot.name.slice(0, 5)}</span>`

      button.appendChild(badge)
      button.addEventListener("click", () => {
        onSelectParkingLot?.(lot)
      })

      const overlay = new kakao.maps.CustomOverlay({
        map,
        position,
        content: button,
        clickable: true,
        zIndex: isSelected ? 12 : 9,
      })
      parkingOverlaysRef.current.push(overlay)
    })
  }, [mapReady, showParking, effectiveParkingLots, selectedParkingLotId, onSelectParkingLot])

  // 선택된 주차장으로 부드럽게 이동
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map || !selectedParkingLotId) return
    const target = effectiveParkingLots.find((p) => p.parking_code === selectedParkingLotId)
    if (!target) return
    map.panTo(new kakao.maps.LatLng(target.latitude, target.longitude))
    map.setLevel(4)
  }, [mapReady, selectedParkingLotId, effectiveParkingLots])

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
        if (!place || id !== searchRequestId.current || !mapRef.current) return
        searchOverlayRef.current?.setMap(null)
        const position = new kakao.maps.LatLng(place.lat, place.lng)
        searchOverlayRef.current = new kakao.maps.CustomOverlay({
          map: mapRef.current,
          position,
          content: makePill(place.name, "#007aff"),
          zIndex: 10,
        })
        mapRef.current.panTo(position)
        mapRef.current.setLevel(4)
      })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [mapReady, searchQuery])

  const focusCurrentLocation = () => {
    const coords = currentPosition.current
    if (!coords || !mapRef.current) {
      setLocationStatus("기기의 위치 서비스를 켠 후 잠시 기다려 주세요.")
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
    <div className="flex flex-col w-full min-w-0 flex-1">
      {/* 지도 상단 컨트롤 바 (지도 밖 상단에 일렬 배치) */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-white/60 border-b border-black/[0.06] backdrop-blur-md">
        {/* 좌측: 서울 전체 / 내 위치 */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleReset}
            className="px-2.5 py-1 text-xs font-semibold rounded-xl bg-white/80 hover:bg-white text-[#007aff] border border-black/[0.08] shadow-xs transition-all flex items-center gap-1 cursor-pointer"
            title="서울 전체 보기"
          >
            <span>◎</span>
            <span>서울 전체</span>
          </button>
          <button
            type="button"
            onClick={focusCurrentLocation}
            className="px-2.5 py-1 text-xs font-semibold rounded-xl bg-white/80 hover:bg-white text-[#007aff] border border-black/[0.08] shadow-xs transition-all flex items-center gap-1 cursor-pointer"
            title="내 위치로 이동"
          >
            <span>📍</span>
            <span>내 위치</span>
          </button>
          {locationStatus && (
            <span className="hidden xl:inline-block text-[11px] text-[#6b6b8a] truncate max-w-[160px] pl-1">
              {locationStatus}
            </span>
          )}
        </div>

        {/* 우측: 돌발상황, 실시간혼잡도, 주차장표시 토글 일렬 나열 */}
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          {/* 1. 돌발상황 토글 */}
          <button
            type="button"
            aria-pressed={showIncidents}
            onClick={() => setShowIncidents((value) => !value)}
            className={`interactive-control px-2.5 sm:px-3 py-1 text-xs font-semibold rounded-xl border shadow-xs flex items-center gap-1.5 cursor-pointer transition-all ${
              showIncidents
                ? "bg-[#ff3b30]/10 border-[#ff3b30]/30 text-[#ff3b30]"
                : "bg-white/70 border-black/[0.08] text-[#6b6b8a]"
            }`}
          >
            <span className={`switch-track incident-switch ${showIncidents ? "is-on" : ""}`}>
              <span className="switch-thumb" />
            </span>
            <span>🚨 돌발상황 {showIncidents ? "ON" : "OFF"}</span>
          </button>

          {/* 2. 실시간혼잡도 토글 */}
          <button
            type="button"
            aria-pressed={showTrafficLines}
            onClick={() => setShowTrafficLines((value) => !value)}
            className={`interactive-control px-2.5 sm:px-3 py-1 text-xs font-semibold rounded-xl border shadow-xs flex items-center gap-1.5 cursor-pointer transition-all ${
              showTrafficLines
                ? "bg-[#007aff]/10 border-[#007aff]/30 text-[#007aff]"
                : "bg-white/70 border-black/[0.08] text-[#6b6b8a]"
            }`}
          >
            <span className={`switch-track ${showTrafficLines ? "is-on" : ""}`}>
              <span className="switch-thumb" />
            </span>
            <span>🚦 실시간혼잡도 {showTrafficLines ? "ON" : "OFF"}</span>
          </button>

          {/* 3. 주차장표시 토글 */}
          <button
            type="button"
            aria-pressed={showParking}
            onClick={() => setShowParking((value) => !value)}
            className={`interactive-control px-2.5 sm:px-3 py-1 text-xs font-semibold rounded-xl border shadow-xs flex items-center gap-1.5 cursor-pointer transition-all ${
              showParking
                ? "bg-[#007aff]/10 border-[#007aff]/30 text-[#007aff]"
                : "bg-white/70 border-black/[0.08] text-[#6b6b8a]"
            }`}
          >
            <span className={`switch-track ${showParking ? "is-on" : ""}`}>
              <span className="switch-thumb" />
            </span>
            <span>🅿️ 주차장표시 {showParking ? "ON" : "OFF"}</span>
          </button>
        </div>
      </div>

      {/* 지도 캔버스 영역 (토글 겹침 없음) */}
      <div
        className="relative overflow-hidden w-full min-w-0 flex-1"
        style={{ minHeight: height, isolation: "isolate" }}
      >
        <div ref={containerRef} className="absolute inset-0" style={{ zIndex: 1 }} />
        {mapError && (
          <div
            role="alert"
            className="absolute inset-0 z-20 flex items-center justify-center bg-white/90 px-6 text-center text-sm text-red-600"
          >
            {mapError}
            <br />
            카카오 JavaScript 키와 등록 도메인을 확인해 주세요.
          </div>
        )}

        {/* 하단 범례 캡슐 */}
        <div
          className="glass absolute bottom-3 left-3 right-3 sm:right-auto z-10 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 shadow-sm"
          style={{ borderRadius: 12 }}
        >
          {[
            { color: "#34c759", label: "원활 (≥50km/h)" },
            { color: "#ff9500", label: "서행 (25~49km/h)" },
            { color: "#ff3b30", label: "혼잡 (<25km/h)" },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-1.5">
              <div
                className="w-3 h-1.5 rounded-full"
                style={{ background: item.color }}
              />
              <span className="text-[11px] font-semibold text-[#4a4a68]">
                {item.label}
              </span>
            </div>
          ))}
          <div className="w-px h-3 bg-black/10 mx-1" />
          <span className="text-[11px] text-[#ff3b30] font-semibold">🚨 사고</span>
          <span className="text-[11px] text-[#ff9500] font-semibold">🚧 공사</span>
          {showParking && effectiveParkingLots.length > 0 && (
            <>
              <div className="w-px h-3 bg-black/10 mx-1" />
              <span className="text-[11px] text-[#007aff] font-semibold">
                🅿️ 주차장 ({effectiveParkingLots.length}곳)
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

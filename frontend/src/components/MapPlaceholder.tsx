import { useCallback, useEffect, useRef, useState } from "react"
import precisionRoadsData from "../data/seoul_roads.json"
import seoulBoundaryData from "../data/seoulBoundary.json"
import { loadKakaoMaps } from "../services/kakaoMaps"
import { resolvePlace } from "../services/placeSearch"
import { fetchNearbyParking, type ParkingLotItem, type RoadSpeedItem } from "../services/api"

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
  roadSpeeds?: RoadSpeedItem[] | Array<{ road: string; speed: number; avg: number; level: string; links?: any[] }>
  selectedIncidentId?: number | string | null
  onSelectIncident?: (incident: IncidentItem) => void
  routeCoordinates?: [number, number][]
  originPoint?: { name: string; lat: number; lng: number }
  destPoint?: { name: string; lat: number; lng: number }
  parkingLots?: ParkingLotItem[]
  selectedParkingLotId?: string | null
  onSelectParkingLot?: (lot: ParkingLotItem) => void
  enableTraffic?: boolean
  enableIncidents?: boolean
  enableParking?: boolean
}

type MapOverlay = kakao.maps.Polyline | kakao.maps.CustomOverlay | kakao.maps.Circle | kakao.maps.Polygon

const EMPTY_INCIDENTS: IncidentItem[] = []
const EMPTY_SPEEDS: RoadSpeedItem[] = []
const EMPTY_PARKING: ParkingLotItem[] = []
const wtmCoordCache = new Map<string, { lat: number; lng: number }>()

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
  incidents = EMPTY_INCIDENTS,
  roadSpeeds = EMPTY_SPEEDS,
  selectedIncidentId = null,
  onSelectIncident,
  routeCoordinates,
  originPoint,
  destPoint,
  parkingLots = EMPTY_PARKING,
  selectedParkingLotId = null,
  onSelectParkingLot,
  enableTraffic = true,
  enableIncidents = true,
  enableParking = true,
}: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<kakao.maps.Map | null>(null)
  const onSelectIncidentRef = useRef(onSelectIncident)
  onSelectIncidentRef.current = onSelectIncident
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
  const [internalSelectedParkingCode, setInternalSelectedParkingCode] = useState<string | null>(null)
  const activeSelectedParkingId = selectedParkingLotId !== undefined && selectedParkingLotId !== null
    ? selectedParkingLotId
    : internalSelectedParkingCode
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
      sdk.maps.event.addListener(map, "click", () => {
        setInternalSelectedParkingCode(null)
      })
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

  const fetchParkingForLocation = useCallback((lat: number, lng: number) => {
    fetchNearbyParking(lat, lng, 4000, 25)
      .then((lots) => setInternalParkingLots(lots))
      .catch((err) => console.warn("Failed to fetch nearby parking:", err))
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
      if (firstFix) {
        if (enableParking && (!parkingLots || parkingLots.length === 0)) {
          fetchParkingForLocation(coords.latitude, coords.longitude)
        }
      }
      firstFix = false
    }, (error) => {
      if (!active) return
      setLocationStatus(error.code === 1
        ? "위치 권한이 꺼져 있습니다. 브라우저 설정에서 허용해 주세요."
        : error.code === 3 ? "위치 확인 시간이 초과되었습니다." : "현재 위치를 확인할 수 없습니다.")
      if (enableParking && (!parkingLots || parkingLots.length === 0) && mapRef.current) {
        const center = mapRef.current.getCenter()
        fetchParkingForLocation(center.getLat(), center.getLng())
      }
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 })
    return () => {
      active = false
      navigator.geolocation.clearWatch(watchId)
      locationOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      locationOverlaysRef.current = []
    }
  }, [mapReady, parkingLots, fetchParkingForLocation, viewHasContext, enableParking])

  // 1. 도로 폴리라인 렌더링 (돌발상황과 완전 분리)
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return
    roadOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
    roadOverlaysRef.current = []

    if (enableTraffic && showTrafficLines) {
      precisionRoadsData.forEach((road) => {
        const match = (roadSpeeds as RoadSpeedItem[]).find(
          (speed) => speed.road.includes(road.name) || road.name.includes(speed.road),
        )
        const coords = road.coordinates as [number, number][]
        const P = coords.length

        // 1) 링크 구간별 속도 데이터가 존재하는 경우 (구간별 분할 렌더링)
        if (match && match.links && match.links.length > 0 && P >= 2) {
          const links = match.links
          const L = links.length
          for (let i = 0; i < L; i++) {
            const startIdx = Math.floor((i * (P - 1)) / L)
            const endIdx = Math.min(P - 1, Math.floor(((i + 1) * (P - 1)) / L))
            if (endIdx <= startIdx && startIdx < P - 1) continue
            const subCoords = coords.slice(startIdx, endIdx + 1)
            if (subCoords.length < 2) continue

            const linkData = links[i]
            const color =
              linkData.speed < 25 ? "#ff3b30" : linkData.speed < 50 ? "#ff9500" : "#34c759"
            const path = subCoords.map(([lat, lng]) => new kakao.maps.LatLng(lat, lng))

            const outline = new kakao.maps.Polyline({
              map,
              path,
              strokeColor: "#ffffff",
              strokeWeight: 7,
              strokeOpacity: 0.88,
              zIndex: 2,
            })
            const line = new kakao.maps.Polyline({
              map,
              path,
              strokeColor: color,
              strokeWeight: 4,
              strokeOpacity: 0.95,
              zIndex: 3,
            })
            roadOverlaysRef.current.push(outline, line)
          }
        } else if (match && typeof match.speed === "number" && P >= 2) {
          // 2) 도로 단일 평균 속도만 존재하는 경우
          const color = match.speed < 25 ? "#ff3b30" : match.speed < 50 ? "#ff9500" : "#34c759"
          const path = coords.map(([lat, lng]) => new kakao.maps.LatLng(lat, lng))
          const outline = new kakao.maps.Polyline({
            map,
            path,
            strokeColor: "#ffffff",
            strokeWeight: 7,
            strokeOpacity: 0.88,
            zIndex: 2,
          })
          const line = new kakao.maps.Polyline({
            map,
            path,
            strokeColor: color,
            strokeWeight: 4,
            strokeOpacity: 0.92,
            zIndex: 3,
          })
          roadOverlaysRef.current.push(outline, line)
        }
      })
    }
    return () => {
      roadOverlaysRef.current.forEach((overlay) => overlay.setMap(null))
      roadOverlaysRef.current = []
    }
  }, [mapReady, enableTraffic, showTrafficLines, roadSpeeds])

  // 2. 돌발상황 마커 렌더링 (Diffing 방식: 이미 존재하는 마커는 유지하여 깜빡임 원천 제거)
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) return

    if (!enableIncidents || !showIncidents) {
      incidentOverlaysRef.current.forEach(({ overlay }) => overlay.setMap(null))
      incidentOverlaysRef.current.clear()
      return
    }

    const currentIncidentMap = incidentOverlaysRef.current
    const newIncidentIds = new Set(incidents.map((i) => String(i.id)))

    // 1) 제거된 돌발상황만 지도에서 언마운트
    for (const [id, item] of currentIncidentMap.entries()) {
      if (!newIncidentIds.has(id)) {
        item.overlay.setMap(null)
        currentIncidentMap.delete(id)
      }
    }

    // 2) 신규 돌발상황만 마커 생성 (기존 마커는 건드리지 않고 그대로 유지)
    let active = true
    const geocoder = new kakao.maps.services.Geocoder()

    const addIncidentMarker = (incident: IncidentItem, lat: number, lng: number) => {
      if (!active || !mapRef.current) return
      const idKey = String(incident.id)
      if (currentIncidentMap.has(idKey)) return

      const position = new kakao.maps.LatLng(lat, lng)
      const isAccident = incident.type === "사고"
      const isConstruction = incident.type === "공사"
      const color = isAccident ? "#ff3b30" : isConstruction ? "#ff9500" : "#5e5ce6"
      const symbol = isAccident ? "🚨" : isConstruction ? "🚧" : "🚗"
      const button = makePill(symbol, color)
      button.title = `[${incident.type}] ${incident.road} - ${incident.location}`
      button.style.cursor = "pointer"
      button.addEventListener("click", () => onSelectIncidentRef.current?.(incident))
      const overlay = new kakao.maps.CustomOverlay({ map, position, content: button, clickable: true, zIndex: 8 })
      currentIncidentMap.set(idKey, { overlay, lat, lng })
    }

    incidents.forEach((incident) => {
      const idKey = String(incident.id)
      if (currentIncidentMap.has(idKey)) return

      if (typeof incident.lat === "number" && typeof incident.lng === "number") {
        addIncidentMarker(incident, incident.lat, incident.lng)
      } else if (typeof incident.tmX === "number" && typeof incident.tmY === "number") {
        const coordKey = `${incident.tmX}_${incident.tmY}`
        const cached = wtmCoordCache.get(coordKey)
        if (cached) {
          addIncidentMarker(incident, cached.lat, cached.lng)
        } else {
          geocoder.transCoord(
            incident.tmX,
            incident.tmY,
            (results, status) => {
              if (!active) return
              if (status === kakao.maps.services.Status.OK && results[0]) {
                const lat = Number(results[0].y)
                const lng = Number(results[0].x)
                wtmCoordCache.set(coordKey, { lat, lng })
                addIncidentMarker(incident, lat, lng)
              }
            },
            {
              input_coord: kakao.maps.services.Coords.WTM,
              output_coord: kakao.maps.services.Coords.WGS84,
            },
          )
        }
      }
    })

    return () => {
      active = false
    }
  }, [incidents, mapReady, showIncidents, enableIncidents])

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

      // 선택된 돌발상황 위치에 선명하고 안정적인 하이라이트 오버레이 (깜빡임 애니메이션 배제)
      const pulseEl = document.createElement("div")
      pulseEl.style.cssText = "position: relative; display: flex; align-items: center; justify-content: center; pointer-events: none;"
      pulseEl.innerHTML = `
        <div style="position: absolute; width: 44px; height: 44px; border-radius: 50%; background: rgba(255, 59, 48, 0.2); border: 2px solid rgba(255, 59, 48, 0.7); box-shadow: 0 0 14px rgba(255, 59, 48, 0.5);"></div>
        <div style="position: absolute; width: 28px; height: 28px; border-radius: 50%; background: #ff3b30; border: 2px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.35);"></div>
        <div style="position: relative; z-index: 2; font-size: 14px; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.4));">${incident?.type === "사고" ? "🚨" : incident?.type === "공사" ? "🚧" : "⚠️"}</div>
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

  // 주차장 토글 시 데이터가 없으면 현재 내 위치(우선) 또는 지도 중심 좌표 기준 주차장 조회
  useEffect(() => {
    if (enableParking && showParking && (!parkingLots || parkingLots.length === 0) && internalParkingLots.length === 0 && mapReady) {
      if (currentPosition.current) {
        fetchParkingForLocation(currentPosition.current.latitude, currentPosition.current.longitude)
      } else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          ({ coords }) => {
            currentPosition.current = coords
            fetchParkingForLocation(coords.latitude, coords.longitude)
          },
          () => {
            const center = mapRef.current?.getCenter()
            if (center) fetchParkingForLocation(center.getLat(), center.getLng())
          },
          { enableHighAccuracy: true, timeout: 5000, maximumAge: 10000 }
        )
      } else {
        const center = mapRef.current?.getCenter()
        if (center) fetchParkingForLocation(center.getLat(), center.getLng())
      }
    }
  }, [showParking, parkingLots, internalParkingLots.length, mapReady, fetchParkingForLocation, enableParking])

  // 주차장 마커 및 선택 시 상세 정보 팝업 렌더링
  useEffect(() => {
    const map = mapRef.current
    parkingOverlaysRef.current.forEach((o) => o.setMap(null))
    parkingOverlaysRef.current = []

    if (!mapReady || !map || !enableParking || !showParking || !effectiveParkingLots.length) return

    effectiveParkingLots.forEach((lot) => {
      const position = new kakao.maps.LatLng(lot.latitude, lot.longitude)
      const hasLive = lot.realtime_status === "AVAILABLE" && lot.available_spaces !== null
      const isSelected = activeSelectedParkingId === lot.parking_code

      const container = document.createElement("div")
      container.className = "relative flex flex-col items-center"
      container.style.zIndex = isSelected ? "30" : "10"

      // 1. 선택되었을 때 상세 정보 팝업 카드 (마커 바로 위에 부드럽게 표시)
      if (isSelected) {
        const popup = document.createElement("div")
        popup.className = "absolute bottom-full mb-2.5 z-30 pointer-events-auto"
        popup.style.minWidth = "230px"
        popup.style.maxWidth = "270px"
        popup.style.cursor = "default"

        popup.innerHTML = `
          <div style="background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 16px; padding: 12px 14px; box-shadow: 0 14px 32px rgba(0, 0, 0, 0.22), 0 2px 8px rgba(0, 0, 0, 0.08); text-align: left;">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; border-bottom: 1px solid rgba(0, 0, 0, 0.06); padding-bottom: 8px; margin-bottom: 8px;">
              <div style="min-width: 0; flex: 1;">
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="font-size: 13px;">🅿️</span>
                  <span style="font-weight: 700; font-size: 13px; color: #1a1a2e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; max-width: 175px;" title="${lot.name}">${lot.name}</span>
                </div>
                <div style="font-size: 10px; color: #6b6b8a; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 175px;" title="${lot.address}">${lot.address || "주소 정보 없음"}</div>
              </div>
              <button type="button" class="parking-close-btn" style="background: none; border: none; padding: 3px; cursor: pointer; color: #8e8e93; border-radius: 6px; display: flex; align-items: center; justify-content: center;" aria-label="닫기" title="닫기">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            <div style="display: flex; flex-direction: column; gap: 5px; font-size: 11px;">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="color: #6b6b8a;">실시간 현황</span>
                <span style="font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 6px; ${
                  hasLive
                    ? "background: #ecfdf5; color: #065f46; border: 1px solid rgba(16, 185, 129, 0.3);"
                    : "background: #f1f5f9; color: #64748b; border: 1px solid rgba(148, 163, 184, 0.3);"
                }">
                  ${hasLive ? `🟢 가능 ${lot.available_spaces}대` : "⚪ 실시간 미지원"}
                </span>
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="color: #6b6b8a;">총 주차면수</span>
                <span style="font-weight: 600; color: #1a1a2e;">${lot.capacity ? `${lot.capacity}면` : "정보 없음"}</span>
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="color: #6b6b8a;">요금 구분</span>
                <span style="font-weight: 600; color: #1a1a2e;">${lot.paid ? "💳 유료 주차장" : "🆓 무료 주차장"}</span>
              </div>

              ${lot.distance_m ? `
              <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid rgba(0, 0, 0, 0.05); padding-top: 5px; margin-top: 2px;">
                <span style="color: #6b6b8a;">내 위치와의 거리</span>
                <span style="font-weight: 700; color: #007aff;">${lot.distance_m < 1000 ? `${lot.distance_m}m` : `${(lot.distance_m / 1000).toFixed(1)}km`}</span>
              </div>` : ""}
            </div>

            <!-- 말풍선 꼬리 화살표 -->
            <div style="position: absolute; bottom: -5px; left: 50%; transform: translateX(-50%) rotate(45deg); width: 10px; height: 10px; background: rgba(255, 255, 255, 0.96); border-right: 1px solid rgba(0, 0, 0, 0.12); border-bottom: 1px solid rgba(0, 0, 0, 0.12);"></div>
          </div>
        `

        const closeBtn = popup.querySelector(".parking-close-btn") as HTMLButtonElement | null
        if (closeBtn) {
          closeBtn.addEventListener("click", (e) => {
            e.stopPropagation()
            setInternalSelectedParkingCode(null)
          })
        }

        container.appendChild(popup)
      }

      // 2. 주차장 마커 뱃지 (선택 시 자연스럽게 커짐)
      const button = document.createElement("button")
      button.type = "button"
      button.className = "group relative flex items-center cursor-pointer transition-all duration-300"
      button.setAttribute("aria-label", `${lot.name} 주차장`)

      const badge = document.createElement("div")
      badge.className = "flex items-center gap-1 px-2.5 py-1 rounded-xl font-bold border transition-all duration-300"
      badge.style.fontSize = "11px"

      if (isSelected) {
        // 선택 시 자연스럽게 커짐 (scale 1.18 및 반짝이는 링 효과)
        badge.style.transform = "scale(1.18)"
        badge.style.background = hasLive 
          ? "linear-gradient(135deg, #10b981, #059669)" 
          : "linear-gradient(135deg, #007aff, #0051d4)"
        badge.style.color = "#ffffff"
        badge.style.borderColor = "#ffffff"
        badge.style.boxShadow = "0 0 0 3px rgba(255,255,255,0.95), 0 0 16px rgba(0, 122, 255, 0.55), 0 8px 18px rgba(0,0,0,0.3)"
      } else {
        badge.style.transform = "scale(1.0)"
        badge.style.background = hasLive ? "#059669" : "#2c3e50"
        badge.style.color = "#ffffff"
        badge.style.borderColor = "rgba(255, 255, 255, 0.85)"
        badge.style.boxShadow = "0 2px 6px rgba(0,0,0,0.25)"
      }

      badge.innerHTML = `<span>🅿️</span><span>${hasLive ? `${lot.available_spaces}대` : lot.name.slice(0, 5)}</span>`
      button.appendChild(badge)

      button.addEventListener("click", (e) => {
        e.stopPropagation()
        setInternalSelectedParkingCode((prev) => (prev === lot.parking_code ? null : lot.parking_code))
        onSelectParkingLot?.(lot)
      })

      container.appendChild(button)

      const overlay = new kakao.maps.CustomOverlay({
        map,
        position,
        content: container,
        clickable: true,
        zIndex: isSelected ? 30 : 10,
      })
      parkingOverlaysRef.current.push(overlay)
    })
  }, [mapReady, showParking, effectiveParkingLots, activeSelectedParkingId, onSelectParkingLot, enableParking])

  // 선택된 주차장으로 부드럽게 시점 이동 (줌 레벨은 억지로 바꾸지 않고 중심만 이동)
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map || !activeSelectedParkingId) return
    const target = effectiveParkingLots.find((p) => p.parking_code === activeSelectedParkingId)
    if (!target) return
    map.panTo(new kakao.maps.LatLng(target.latitude, target.longitude))
  }, [mapReady, activeSelectedParkingId, effectiveParkingLots])

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
    if (enableParking && (!parkingLots || parkingLots.length === 0)) {
      fetchParkingForLocation(coords.latitude, coords.longitude)
    }
  }

  const handleReset = () => {
    if (!mapRef.current) return
    mapRef.current.setCenter(new kakao.maps.LatLng(37.5320, 126.9950))
    mapRef.current.setLevel(8)
  }

  return (
    <div className="flex flex-col w-full min-w-0 flex-1">
      {/* 지도 상단 컨트롤 바 (지도 밖 상단에 일렬 배치) */}
      <div className="flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 bg-white/70 border-b border-black/[0.06] backdrop-blur-md">
        {/* 좌측: 서울 전체 / 내 위치 */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleReset}
            className="px-2 py-0.5 text-[11px] font-semibold rounded-lg bg-white/90 hover:bg-white text-[#007aff] border border-black/[0.08] shadow-2xs transition-all flex items-center gap-1 cursor-pointer"
            title="서울 전체 보기"
          >
            <span className="text-[10px]">◎</span>
            <span>서울 전체</span>
          </button>
          <button
            type="button"
            onClick={focusCurrentLocation}
            className="px-2 py-0.5 text-[11px] font-semibold rounded-lg bg-white/90 hover:bg-white text-[#007aff] border border-black/[0.08] shadow-2xs transition-all flex items-center gap-1 cursor-pointer"
            title="내 위치로 이동"
          >
            <span className="text-[10px]">📍</span>
            <span>내 위치</span>
          </button>
          {locationStatus && (
            <span className="hidden xl:inline-block text-[10px] text-[#6b6b8a] truncate max-w-[140px] pl-1">
              {locationStatus}
            </span>
          )}
        </div>

        {/* 우측: 돌발상황, 실시간혼잡도, 주차장표시 토글 일렬 나열 (슬림 & 컴팩트) */}
        {(enableIncidents || enableTraffic || enableParking) && (
          <div className="liquid-glass-capsule p-1 flex flex-wrap items-center gap-1 rounded-xl">
            {/* 1. 돌발상황 토글 아이템 */}
            {enableIncidents && (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                <span className="text-[11px] font-medium text-white/90 flex items-center gap-1 select-none">
                  <span>🚨 돌발상황</span>
                  <span
                    className={`text-[9px] font-bold px-1 py-0.2 rounded transition-colors ${
                      showIncidents
                        ? "text-[#ff453a] bg-[#ff453a]/20 border border-[#ff453a]/30"
                        : "text-white/40 bg-white/[0.06]"
                    }`}
                  >
                    {showIncidents ? "ON" : "OFF"}
                  </span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={showIncidents}
                  onClick={() => setShowIncidents((value) => !value)}
                  className="relative inline-flex items-center h-4 w-7 shrink-0 cursor-pointer rounded-full border transition-all duration-200 focus:outline-none"
                  style={{
                    background: showIncidents
                      ? "linear-gradient(135deg, #ff3b30, #ff6259)"
                      : "rgba(255, 255, 255, 0.15)",
                    borderColor: showIncidents
                      ? "rgba(255, 99, 90, 0.6)"
                      : "rgba(255, 255, 255, 0.28)",
                    boxShadow: showIncidents
                      ? "0 0 8px rgba(255, 59, 48, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.35)"
                      : "inset 0 1px 2px rgba(0, 0, 0, 0.4)",
                  }}
                  title={`돌발상황 ${showIncidents ? "끄기" : "켜기"}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-2.5 w-2.5 transform rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                      showIncidents ? "translate-x-3.5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            )}

            {enableIncidents && enableTraffic && <div className="w-px h-3.5 bg-white/15 hidden sm:block" />}

            {/* 2. 실시간혼잡도 토글 아이템 */}
            {enableTraffic && (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                <span className="text-[11px] font-medium text-white/90 flex items-center gap-1 select-none">
                  <span>🚦 실시간혼잡도</span>
                  <span
                    className={`text-[9px] font-bold px-1 py-0.2 rounded transition-colors ${
                      showTrafficLines
                        ? "text-[#38bdf8] bg-[#007aff]/20 border border-[#007aff]/30"
                        : "text-white/40 bg-white/[0.06]"
                    }`}
                  >
                    {showTrafficLines ? "ON" : "OFF"}
                  </span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={showTrafficLines}
                  onClick={() => setShowTrafficLines((value) => !value)}
                  className="relative inline-flex items-center h-4 w-7 shrink-0 cursor-pointer rounded-full border transition-all duration-200 focus:outline-none"
                  style={{
                    background: showTrafficLines
                      ? "linear-gradient(135deg, #007aff, #38bdf8)"
                      : "rgba(255, 255, 255, 0.15)",
                    borderColor: showTrafficLines
                      ? "rgba(56, 189, 248, 0.6)"
                      : "rgba(255, 255, 255, 0.28)",
                    boxShadow: showTrafficLines
                      ? "0 0 8px rgba(0, 122, 255, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.35)"
                      : "inset 0 1px 2px rgba(0, 0, 0, 0.4)",
                  }}
                  title={`실시간혼잡도 ${showTrafficLines ? "끄기" : "켜기"}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-2.5 w-2.5 transform rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                      showTrafficLines ? "translate-x-3.5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            )}

            {enableParking && (enableIncidents || enableTraffic) && <div className="w-px h-3.5 bg-white/15 hidden sm:block" />}

            {/* 3. 주차장표시 토글 아이템 */}
            {enableParking && (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                <span className="text-[11px] font-medium text-white/90 flex items-center gap-1 select-none">
                  <span>🅿️ 주차장</span>
                  <span
                    className={`text-[9px] font-bold px-1 py-0.2 rounded transition-colors ${
                      showParking
                        ? "text-[#38bdf8] bg-[#007aff]/20 border border-[#007aff]/30"
                        : "text-white/40 bg-white/[0.06]"
                    }`}
                  >
                    {showParking ? "ON" : "OFF"}
                  </span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={showParking}
                  onClick={() => setShowParking((value) => !value)}
                  className="relative inline-flex items-center h-4 w-7 shrink-0 cursor-pointer rounded-full border transition-all duration-200 focus:outline-none"
                  style={{
                    background: showParking
                      ? "linear-gradient(135deg, #007aff, #38bdf8)"
                      : "rgba(255, 255, 255, 0.15)",
                    borderColor: showParking
                      ? "rgba(56, 189, 248, 0.6)"
                      : "rgba(255, 255, 255, 0.28)",
                    boxShadow: showParking
                      ? "0 0 8px rgba(0, 122, 255, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.35)"
                      : "inset 0 1px 2px rgba(0, 0, 0, 0.4)",
                  }}
                  title={`주차장 표시 ${showParking ? "끄기" : "켜기"}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-2.5 w-2.5 transform rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                      showParking ? "translate-x-3.5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            )}
          </div>
        )}
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

        {/* 하단 범례 캡슐 (활성화된 레이어만 표시) */}
        {((enableTraffic && showTrafficLines) ||
          (enableIncidents && showIncidents) ||
          (enableParking && showParking && effectiveParkingLots.length > 0)) && (
          <div
            className="glass absolute bottom-3 left-3 right-3 sm:right-auto z-10 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 shadow-sm"
            style={{ borderRadius: 12 }}
          >
            {enableTraffic &&
              showTrafficLines &&
              [
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
            {enableTraffic && showTrafficLines && enableIncidents && showIncidents && (
              <div className="w-px h-3 bg-black/10 mx-1" />
            )}
            {enableIncidents && showIncidents && (
              <>
                <span className="text-[11px] text-[#ff3b30] font-semibold">🚨 사고</span>
                <span className="text-[11px] text-[#ff9500] font-semibold">🚧 공사</span>
              </>
            )}
            {enableParking && showParking && effectiveParkingLots.length > 0 && (
              <>
                {(enableTraffic || enableIncidents) && <div className="w-px h-3 bg-black/10 mx-1" />}
                <span className="text-[11px] text-[#007aff] font-semibold">
                  🅿️ 주차장 ({effectiveParkingLots.length}곳)
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

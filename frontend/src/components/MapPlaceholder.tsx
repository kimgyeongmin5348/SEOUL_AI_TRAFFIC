import { useEffect, useRef, useState } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import precisionRoadsData from "../data/seoul_roads.json"

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
  roadSpeeds?: Array<{
    road: string
    speed: number
    avg: number
    level: string
  }>
  selectedIncidentId?: number | string | null
  onSelectIncident?: (incident: IncidentItem) => void
  routeCoordinates?: [number, number][]
  originPoint?: { name: string; lat: number; lng: number }
  destPoint?: { name: string; lat: number; lng: number }
}

// 서울 주요 랜드마크 검색 좌표
const SEOUL_PLACES: Record<string, { lat: number; lng: number; zoom: number; name: string }> = {
  "강남": { lat: 37.4979, lng: 127.0276, zoom: 15, name: "강남역 / 테헤란로" },
  "강남역": { lat: 37.4979, lng: 127.0276, zoom: 15, name: "강남역 교차로" },
  "역삼": { lat: 37.5006, lng: 127.0365, zoom: 15, name: "역삼역 사거리" },
  "여의도": { lat: 37.5255, lng: 126.9242, zoom: 15, name: "여의도 금융 중심지" },
  "마포": { lat: 37.5458, lng: 126.9525, zoom: 15, name: "마포구 마포대로" },
  "합정": { lat: 37.5495, lng: 126.9138, zoom: 15, name: "합정역 교차로" },
  "홍대": { lat: 37.5563, lng: 126.9226, zoom: 15, name: "홍대입구역" },
  "종로": { lat: 37.5704, lng: 126.9922, zoom: 15, name: "종로구 중심" },
  "광화문": { lat: 37.5759, lng: 126.9768, zoom: 15, name: "광화문 광장" },
  "잠실": { lat: 37.5133, lng: 127.1001, zoom: 15, name: "잠실역 / 송파대로" },
  "송파": { lat: 37.5048, lng: 127.1145, zoom: 14, name: "송파구 중심" },
  "서초": { lat: 37.4919, lng: 127.0078, zoom: 15, name: "서초역 / 반포대로" },
  "용산": { lat: 37.5326, lng: 126.9900, zoom: 15, name: "용산구 / 이태원" },
  "영등포": { lat: 37.5180, lng: 126.9070, zoom: 15, name: "영등포역 교차로" },
  "구로": { lat: 37.4980, lng: 126.8870, zoom: 15, name: "신도림 / 구로디지털단지" },
  "강변북로": { lat: 37.5315, lng: 126.9660, zoom: 13, name: "강변북로" },
  "올림픽대로": { lat: 37.5150, lng: 126.9850, zoom: 13, name: "올림픽대로" },
  "내부순환로": { lat: 37.6010, lng: 126.9950, zoom: 13, name: "내부순환로" },
  "동부간선": { lat: 37.5650, lng: 127.0700, zoom: 13, name: "동부간선도로" },
  "서부간선": { lat: 37.4980, lng: 126.8830, zoom: 13, name: "서부간선도로" },
  "경부고속": { lat: 37.4850, lng: 127.0250, zoom: 13, name: "경부고속도로" },
  "분당수서": { lat: 37.5020, lng: 127.0720, zoom: 14, name: "분당수서로" },
  "양재대로": { lat: 37.4720, lng: 127.0500, zoom: 14, name: "양재대로" },
  "영동대로": { lat: 37.5120, lng: 127.0600, zoom: 14, name: "영동대로" },
  "새문안로": { lat: 37.5690, lng: 126.9720, zoom: 15, name: "새문안로" },
}

// 각 도로별 라벨이 가장 예쁘게 보일 중심 좌표
const ROAD_LABEL_POINTS: Record<string, [number, number]> = {
  "강변북로": [37.5330, 126.9600], // 원효~한강대교 북단
  "올림픽대로": [37.5130, 126.9800], // 동작대교 남단
  "내부순환로": [37.6040, 126.9940], // 정릉터널 앞
  "분당수서로": [37.5020, 127.0720], // 탄천1교 부근
  "새문안로": [37.5695, 126.9740], // 광화문 앞
  "양재대로": [37.4750, 127.0600], // 구룡터널 사거리
  "영동대로": [37.5110, 127.0600], // 코엑스 앞
  "경부고속도로": [37.4950, 127.0220], // 반포IC
  "동부간선도로": [37.5850, 127.0730], // 중랑교
  "서부간선도로": [37.4980, 126.8830], // 신도림교
  "테헤란로": [37.5020, 127.0420], // 역삼~선릉 사이
}

// 돌발상황 위치 키워드 기반 정밀 좌표 사전
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
  const mapRef = useRef<L.Map | null>(null)
  const searchMarkerRef = useRef<L.Marker | null>(null)
  const layersGroupRef = useRef<L.LayerGroup | null>(null)
  const routeLayerGroupRef = useRef<L.LayerGroup | null>(null)
  const incidentMarkersRef = useRef<Map<string | number, { marker: L.Marker; lat: number; lng: number }>>(new Map())
  const [showTrafficLines, setShowTrafficLines] = useState(true)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [37.5320, 126.9950],
      zoom: 12,
      zoomControl: false,
      attributionControl: false,
    })

    // 고해상도 도로망 중심 타일 레이어 (워터마크 없는 깔끔한 표준 OSM 타일)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      subdomains: ["a", "b", "c"],
    }).addTo(map)

    L.control.zoom({ position: "topright" }).addTo(map)

    const layerGroup = L.layerGroup().addTo(map)
    layersGroupRef.current = layerGroup

    const routeLayerGroup = L.layerGroup().addTo(map)
    routeLayerGroupRef.current = routeLayerGroup

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      layersGroupRef.current = null
      routeLayerGroupRef.current = null
    }
  }, [])

  // 도로 정밀 궤적(seoul_roads.json) 및 실시간 DB 속도 매핑
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = layersGroupRef.current
    if (!map || !layerGroup) return

    layerGroup.clearLayers()
    incidentMarkersRef.current.clear()

    if (showTrafficLines) {
      precisionRoadsData.forEach((r) => {
        // DB 속도 매칭 (도로명 또는 road_name 부분 매칭)
        const matchSpeed = roadSpeeds.find(
          (s) => s.road.includes(r.name) || r.name.includes(s.road)
        )
        const speed = matchSpeed ? matchSpeed.speed : r.defaultSpeed
        let color = "#34c759" // 원활
        let label = "원활"
        if (speed < 25) {
          color = "#ff3b30" // 혼잡
          label = "혼잡"
        } else if (speed < 50) {
          color = "#ff9500" // 서행
          label = "서행"
        }

        const coords = r.coordinates as [number, number][]

        // 1. 도로 테두리 아웃라인 (도로 폭에 정확히 일치하도록 5px)
        L.polyline(coords, {
          color: "#ffffff",
          weight: 6,
          opacity: 0.9,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(layerGroup)

        // 2. 실시간 혼잡도 색상 도로선 (실제 도로 중심선에 1:1 매핑)
        const poly = L.polyline(coords, {
          color,
          weight: 4,
          opacity: 0.92,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(layerGroup)

        const popupContent = `
          <div style="font-family: sans-serif; font-size: 13px; line-height: 1.5; min-width: 140px;">
            <strong style="color: #1a1a2e; font-size: 14px;">${r.name}</strong><br/>
            <span>실시간 통행 상태: </span>
            <span style="color: ${color}; font-weight: 700;">${label} (${speed} km/h)</span>
          </div>
        `
        poly.bindPopup(popupContent)
        poly.bindTooltip(`${r.name}: ${label} (${speed}km/h)`, { sticky: true, opacity: 0.9 })
      })
    }

    // DB 돌발상황 마커
    if (incidents && incidents.length > 0) {
      incidents.forEach((inc) => {
        const [lat, lng] = getIncidentCoord(inc)
        const isAccident = inc.type === "사고"
        const isConstruction = inc.type === "공사"
        const badgeColor = isAccident ? "#ff3b30" : isConstruction ? "#ff9500" : "#5e5ce6"
        const emoji = isAccident ? "🚨" : isConstruction ? "🚧" : "🚗"

        const incIcon = L.divIcon({
          className: "incident-pin",
          html: `
            <div style="
              background: ${badgeColor};
              color: white;
              width: 28px;
              height: 28px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 14px;
              border: 2px solid white;
              box-shadow: 0 4px 12px rgba(0,0,0,0.3);
              cursor: pointer;
              transform: translate(-50%, -50%);
            ">
              ${emoji}
            </div>
          `,
          iconSize: [0, 0],
        })

        const marker = L.marker([lat, lng], { icon: incIcon }).addTo(layerGroup)
        marker.bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px; line-height: 1.5; max-width: 240px;">
            <div style="font-weight: 700; color: ${badgeColor}; font-size: 13px; margin-bottom: 3px; display: flex; items-center; gap: 4px;">
              <span>${emoji}</span> [${inc.type}] ${inc.road}
            </div>
            <div style="color: #2b2b3d; margin-bottom: 5px; font-weight: 500;">${inc.description || inc.location}</div>
            <div style="color: #6b6b8a; font-size: 11px;">
              <span>발생: ${inc.startTime || "최근"}</span>
              ${inc.estEnd ? ` · 해제: ${inc.estEnd}` : ""}
            </div>
          </div>
        `)

        marker.on("click", () => {
          onSelectIncident?.(inc)
        })

        incidentMarkersRef.current.set(inc.id, { marker, lat, lng })
      })
    }
  }, [roadSpeeds, incidents, onSelectIncident, showTrafficLines])

  // 실제 주행 경로 오버레이
  useEffect(() => {
    const map = mapRef.current
    const rGroup = routeLayerGroupRef.current
    if (!map || !rGroup) return

    rGroup.clearLayers()

    if (routeCoordinates && routeCoordinates.length > 1) {
      // 아웃라인
      L.polyline(routeCoordinates, {
        color: "#ffffff",
        weight: 8,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(rGroup)

      // 네비게이션 경로선 (도로 중심선 완벽 밀착)
      const routePoly = L.polyline(routeCoordinates, {
        color: "#007aff",
        weight: 5.5,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(rGroup)

      if (originPoint) {
        const startIcon = L.divIcon({
          className: "start-pin",
          html: `<div style="background: #34c759; color: white; padding: 4px 10px; border-radius: 14px; font-size: 11px; font-weight: 700; border: 2px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.3); white-space: nowrap; transform: translate(-50%, -100%);">🟢 출발: ${originPoint.name}</div>`,
          iconSize: [0, 0],
        })
        L.marker([originPoint.lat, originPoint.lng], { icon: startIcon }).addTo(rGroup)
      }

      if (destPoint) {
        const endIcon = L.divIcon({
          className: "end-pin",
          html: `<div style="background: #ff3b30; color: white; padding: 4px 10px; border-radius: 14px; font-size: 11px; font-weight: 700; border: 2px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.3); white-space: nowrap; transform: translate(-50%, -100%);">🏁 도착: ${destPoint.name}</div>`,
          iconSize: [0, 0],
        })
        L.marker([destPoint.lat, destPoint.lng], { icon: endIcon }).addTo(rGroup)
      }

      map.fitBounds(routePoly.getBounds(), {
        padding: [45, 45],
        maxZoom: 15,
        animate: true,
      })
    }
  }, [routeCoordinates, originPoint, destPoint])

  // 공사/사고 선택 시 이동
  useEffect(() => {
    const map = mapRef.current
    if (!map || selectedIncidentId === null || selectedIncidentId === undefined) return

    const item = incidentMarkersRef.current.get(selectedIncidentId)
    if (item) {
      map.flyTo([item.lat, item.lng], 15, {
        duration: 1.2,
      })
      setTimeout(() => {
        item.marker.openPopup()
      }, 700)
    }
  }, [selectedIncidentId])

  // 검색 이동
  useEffect(() => {
    const map = mapRef.current
    if (!map || !searchQuery || !searchQuery.trim()) return

    const q = searchQuery.trim().toLowerCase()
    const foundKey = Object.keys(SEOUL_PLACES).find(
      (k) => q.includes(k.toLowerCase()) || k.toLowerCase().includes(q)
    )

    if (foundKey) {
      const target = SEOUL_PLACES[foundKey]
      map.flyTo([target.lat, target.lng], target.zoom, {
        duration: 1.2,
      })

      if (searchMarkerRef.current) {
        searchMarkerRef.current.remove()
      }

      const customIcon = L.divIcon({
        className: "custom-pin",
        html: `
          <div style="
            background: #007aff;
            color: white;
            padding: 6px 14px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 700;
            white-space: nowrap;
            box-shadow: 0 4px 16px rgba(0,122,255,0.45);
            border: 2px solid white;
            display: flex;
            align-items: center;
            gap: 5px;
            transform: translate(-50%, -100%);
          ">
            <span>📍</span> ${target.name}
          </div>
        `,
        iconSize: [0, 0],
      })

      const marker = L.marker([target.lat, target.lng], { icon: customIcon }).addTo(map)
      marker.bindPopup(`<b>${target.name}</b><br/>실시간 교통 모니터링 중`).openPopup()
      searchMarkerRef.current = marker
    }
  }, [searchQuery])

  const handleReset = () => {
    mapRef.current?.flyTo([37.5320, 126.9950], 12, { duration: 1 })
  }

  return (
    <div
      className="relative overflow-hidden w-full"
      style={{ height, minHeight: 380 }}
    >
      <div ref={containerRef} className="w-full h-full" style={{ zIndex: 1 }} />

      {/* 좌측 상단 빠른 복귀 버튼 */}
      <div
        className="absolute top-3 left-3 z-10 glass px-3 py-1.5 flex items-center gap-2 cursor-pointer hover:bg-white/95 transition-all shadow-sm"
        style={{ borderRadius: 12 }}
        onClick={handleReset}
        title="서울 전체로 이동"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#007aff" strokeWidth="2.2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
          <path d="M2 12h20" />
        </svg>
        <span
          className="text-xs font-semibold text-[#007aff]"
          style={{ fontFamily: "var(--font-body)" }}
        >
          서울 전체 보기
        </span>
      </div>

      {/* 우측 레이어 컨트롤 버튼 */}
      <div
        className="absolute top-3 right-14 z-10 flex items-center gap-2"
      >
        <button
          onClick={() => setShowTrafficLines(!showTrafficLines)}
          className="glass px-3 py-1.5 text-xs font-semibold rounded-xl cursor-pointer hover:bg-white/90 transition-all shadow-sm flex items-center gap-1.5"
          style={{ color: showTrafficLines ? "#007aff" : "#6b6b8a" }}
        >
          <span className={`w-2 h-2 rounded-full ${showTrafficLines ? "bg-[#007aff]" : "bg-gray-400"}`} />
          실시간 혼잡도 {showTrafficLines ? "ON" : "OFF"}
        </button>
      </div>

      {/* 범례 */}
      <div
        className="glass absolute bottom-3 left-3 z-10 flex items-center gap-3 px-3 py-2 shadow-sm"
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
            <span
              style={{
                fontSize: 11,
                color: "#4a4a68",
                fontFamily: "var(--font-body)",
                fontWeight: 600,
              }}
            >
              {item.label}
            </span>
          </div>
        ))}
        <div className="w-px h-3 bg-black/10 mx-1" />
        <span className="text-[11px] text-[#ff3b30] font-semibold">🚨 사고</span>
        <span className="text-[11px] text-[#ff9500] font-semibold">🚧 공사</span>
      </div>
    </div>
  )
}
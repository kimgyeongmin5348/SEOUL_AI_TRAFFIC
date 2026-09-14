import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import { fetchFavoriteRoutes, FavoriteRouteItem } from "../services/api"

const statusColor: Record<string, string> = {
  green: "#34c759",
  yellow: "#ff9500",
  red: "#ff3b30",
}

const statusLabel: Record<string, string> = {
  green: "원활",
  yellow: "서행",
  red: "정체",
}

export default function Favorites() {
  const navigate = useNavigate()
  const [favoriteList, setFavoriteList] = useState<FavoriteRouteItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchFavoriteRoutes().then((res) => {
      if (active) {
        setFavoriteList(res.routes)
        setLoading(false)
      }
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="min-h-full flex relative" style={{ minHeight: "100dvh" }}>
      <SubpageBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 md:pl-28 md:pr-8 px-3 sm:px-6 pb-24 md:pb-8 pt-[max(64px,calc(env(safe-area-inset-top)+56px))] md:pt-6 max-w-7xl mx-auto w-full">
        <div className="animate-slide-up">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1">
            <h1
              className="text-white text-xl sm:text-2xl font-bold tracking-tight"
              style={{
                fontFamily: "var(--font-display)",
                textShadow: "0 2px 12px rgba(0,0,0,0.35)",
              }}
            >
              나의 즐겨찾기 경로
            </h1>
            <span
              className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
              style={{
                background: "rgba(0,122,255,0.2)",
                color: "#60a5fa",
                border: "1px solid rgba(96,165,250,0.3)",
                fontFamily: "var(--font-body)",
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#60a5fa] pulse-dot" />
              내 검색 횟수 상위 4개
            </span>
          </div>
          <p
            className="text-white/70 text-xs sm:text-sm mb-5"
            style={{ fontFamily: "var(--font-body)" }}
          >
            로그인한 계정에서 자주 검색한 경로를 실시간으로 모니터링하고 빠른 분석을 제공합니다.
          </p>
        </div>

        {/* 2-Column Responsive Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Top Favorite Routes List */}
          <div className="lg:col-span-7 flex flex-col gap-3 animate-slide-up-delay-1">
            <div className="flex items-center justify-between mb-0.5 px-1">
              <span className="text-xs font-semibold text-white/80 uppercase tracking-wider">
                자주 찾는 경로 목록
              </span>
              <span className="text-xs text-white/50">클릭 시 즉시 경로 분석</span>
            </div>

            {loading ? (
              <div className="glass p-8 text-center text-[#6b6b8a] text-sm rounded-3xl">
                DB에서 최다 검색 경로를 집계하는 중…
              </div>
            ) : favoriteList.length === 0 ? (
              <div className="glass p-8 text-center text-[#6b6b8a] text-sm rounded-3xl">
                아직 저장된 경로 검색 이력이 없습니다. 경로 분석에서 검색해 보세요!
              </div>
            ) : (
              favoriteList.map((r, idx) => {
                const color = statusColor[r.status] || "#ff9500"
                return (
                  <div
                    key={r.id}
                    className="glass glass-hover item-glide p-4 sm:p-5 cursor-pointer border border-transparent hover:border-[#007aff]/40 shadow-sm"
                    style={{ borderRadius: 22 }}
                    onClick={() =>
                      navigate(
                        `/route?origin=${encodeURIComponent(r.origin)}&dest=${encodeURIComponent(r.destination)}`
                      )
                    }
                    title="클릭 시 이 경로로 즉시 분석합니다"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-start sm:items-center gap-3 min-w-0">
                        <div
                          className="w-10 h-10 sm:w-11 sm:h-11 flex items-center justify-center text-xs sm:text-sm font-bold flex-shrink-0"
                          style={{
                            background:
                              idx === 0
                                ? "linear-gradient(135deg, #ffd700, #ff9500)"
                                : "rgba(240,242,248,0.9)",
                            color: idx === 0 ? "white" : "#4a4a68",
                            borderRadius: 14,
                            boxShadow:
                              idx === 0
                                ? "0 4px 12px rgba(255,149,0,0.3)"
                                : undefined,
                          }}
                        >
                          {idx + 1}위
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 flex-wrap mb-1">
                            <span
                              className="font-semibold text-[#1a1a2e] text-sm sm:text-base truncate"
                              style={{ fontFamily: "var(--font-display)" }}
                            >
                              {r.label}
                            </span>
                            <span
                              className="text-[10px] sm:text-[11px] px-2 py-0.5 rounded-full font-bold text-[#007aff] bg-blue-50 border border-blue-100 flex-shrink-0"
                              style={{ fontFamily: "var(--font-mono)" }}
                            >
                              {r.search_count}회 검색
                            </span>
                            <span
                              className="text-[10px] sm:text-[11px] px-2 py-0.5 rounded-full font-medium flex-shrink-0"
                              style={{
                                background: `${color}15`,
                                color,
                                fontFamily: "var(--font-body)",
                              }}
                            >
                              {statusLabel[r.status]}
                            </span>
                          </div>
                          <p
                            className="text-xs text-[#6b6b8a] truncate"
                            style={{ fontFamily: "var(--font-body)" }}
                          >
                            {r.origin} ➔ {r.destination}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center sm:flex-col sm:items-end justify-between sm:justify-center border-t sm:border-t-0 pt-2 sm:pt-0 border-black/5 flex-shrink-0">
                        <div className="flex items-end gap-1 justify-end">
                          <span
                            className="text-[#1a1a2e]"
                            style={{
                              fontFamily: "var(--font-display)",
                              fontWeight: 700,
                              fontSize: 24,
                              letterSpacing: "-0.02em",
                            }}
                          >
                            {r.currentTime}
                          </span>
                          <span className="text-xs sm:text-sm text-[#6b6b8a] mb-0.5">분</span>
                        </div>
                        <p
                          className="text-[11px] sm:text-xs font-medium"
                          style={{
                            color:
                              r.delta > 5
                                ? "#ff3b30"
                                : r.delta > 0
                                  ? "#ff9500"
                                  : "#34c759",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          평소 {r.avgTime}분 ({r.delta > 0 ? `+${r.delta}분 지연` : "원활"})
                        </p>
                      </div>
                    </div>
                  </div>
                )
              })
            )}

            {/* New route search shortcut button */}
            <button
              onClick={() => navigate("/route")}
              className="glass p-4 sm:p-5 flex items-center gap-3 hover:bg-white/80 transition-colors text-left w-full cursor-pointer"
              style={{
                borderRadius: 22,
                border: "1.5px dashed rgba(0,122,255,0.4)",
              }}
            >
              <div
                className="w-10 h-10 flex items-center justify-center flex-shrink-0"
                style={{ background: "rgba(0,122,255,0.1)", borderRadius: 14 }}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path
                    d="M10 5v10M5 10h10"
                    stroke="#007aff"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <div>
                <p
                  className="font-semibold text-[#007aff]"
                  style={{ fontFamily: "var(--font-display)", fontSize: 15 }}
                >
                  새로운 경로 검색하기
                </p>
                <p
                  className="text-xs text-[#6b6b8a] mt-0.5"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  경로를 검색하면 검색 횟수가 DB에 자동 누적되어 즐겨찾기 순위가 갱신됩니다.
                </p>
              </div>
            </button>
          </div>

          {/* Right Column: Useful Stats & Quick Preset Recommendations */}
          <div className="lg:col-span-5 flex flex-col gap-4 animate-slide-up-delay-2">
            {/* Widget 1: Real-time Route Monitoring Summary */}
            <div className="glass p-4 sm:p-5" style={{ borderRadius: 24 }}>
              <div className="flex items-center justify-between mb-3.5">
                <h3
                  className="font-bold text-[#1a1a2e] text-base"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  📊 즐겨찾기 실시간 교통 요약
                </h3>
                <span className="text-[11px] text-[#007aff] bg-blue-50 px-2 py-0.5 rounded-md font-semibold">
                  LIVE
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2.5 mb-4">
                <div className="p-3 rounded-xl bg-white/60 border border-white/80">
                  <span className="text-[11px] text-[#6b6b8a] block mb-1">등록 경로 수</span>
                  <span className="text-xl font-bold text-[#1a1a2e]" style={{ fontFamily: "var(--font-display)" }}>
                    {favoriteList.length}개
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-white/60 border border-white/80">
                  <span className="text-[11px] text-[#6b6b8a] block mb-1">평균 소요 시간</span>
                  <span className="text-xl font-bold text-[#007aff]" style={{ fontFamily: "var(--font-display)" }}>
                    {favoriteList.length > 0
                      ? Math.round(favoriteList.reduce((acc, cur) => acc + cur.currentTime, 0) / favoriteList.length)
                      : 0}분
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-[#007aff]/5 border border-[#007aff]/15 text-xs text-[#3a3a5a] leading-relaxed">
                <div className="flex items-center gap-1.5 font-semibold text-[#007aff] mb-1">
                  <span>✦ AI 출발 추천 알림</span>
                </div>
                현재 등록된 경로 전반에 서행 구간이 관측됩니다. 평균 지연 시간은 약 3분으로, 주요 간선도로 진입 전 AI 경로 우회를 추천합니다.
              </div>
            </div>

            {/* Widget 2: Quick Recommended Routes */}
            <div className="glass p-4 sm:p-5" style={{ borderRadius: 24 }}>
              <h3
                className="font-bold text-[#1a1a2e] text-base mb-1"
                style={{ fontFamily: "var(--font-display)" }}
              >
                ⚡ 서울 주요 거점 빠른 경로 바로가기
              </h3>
              <p className="text-xs text-[#6b6b8a] mb-3">
                출퇴근 및 이동이잦은 대표 구간을 원클릭으로 분석합니다.
              </p>

              <div className="flex flex-col gap-2">
                {[
                  {
                    name: "강남역 ➔ 광화문",
                    desc: "한남대교 · 남산1호터널 도심 관통",
                    origin: "강남역",
                    dest: "광화문",
                    tag: "출퇴근 코어",
                  },
                  {
                    name: "여의도환승센터 ➔ 판교역",
                    desc: "올림픽대로 · 경부고속도로 테크 축",
                    origin: "여의도환승센터",
                    dest: "판교역",
                    tag: "비즈니스",
                  },
                  {
                    name: "잠실역 ➔ 홍대입구역",
                    desc: "강변북로 동서 횡단 메인 링크",
                    origin: "잠실역",
                    dest: "홍대입구역",
                    tag: "동서축",
                  },
                ].map((item) => (
                  <button
                    key={item.name}
                    type="button"
                    onClick={() =>
                      navigate(
                        `/route?origin=${encodeURIComponent(item.origin)}&dest=${encodeURIComponent(item.dest)}`
                      )
                    }
                    className="item-glide p-3 rounded-xl bg-white/60 hover:bg-white border border-white/80 transition-all text-left flex items-center justify-between group cursor-pointer"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-bold text-[#1a1a2e] group-hover:text-[#007aff] transition-colors">
                          {item.name}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-gray-100 text-[#555]">
                          {item.tag}
                        </span>
                      </div>
                      <span className="text-[11px] text-[#7a7a9a]">{item.desc}</span>
                    </div>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 16 16"
                      fill="none"
                      className="text-[#a0a0b8] group-hover:text-[#007aff] group-hover:translate-x-0.5 transition-all flex-shrink-0"
                    >
                      <path
                        d="M6 3l5 5-5 5"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                ))}
              </div>
            </div>

            {/* Widget 3: Data Sync Info */}
            <div
              className="p-4 rounded-2xl"
              style={{
                background: "rgba(255, 255, 255, 0.5)",
                border: "1px solid rgba(255, 255, 255, 0.7)",
              }}
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-[#1a1a2e] mb-1">
                <span className="w-2 h-2 rounded-full bg-[#34c759]" />
                <span>개인화 경로 자동 동기화 활성화</span>
              </div>
              <p className="text-[11px] text-[#6b6b8a] leading-relaxed">
                경로 분석에서 검색을 실행할 때마다 최근 검색 이력과 누적 횟수가 데이터베이스에 안전하게 기록되어 즐겨찾기 순위에 자동 반영됩니다.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

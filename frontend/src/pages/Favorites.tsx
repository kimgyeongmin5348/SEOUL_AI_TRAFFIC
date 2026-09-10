import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import { fetchFavoriteRoutes, FavoriteRouteItem } from "../services/api"

const statusColor = { green: "#34c759", yellow: "#ff9500", red: "#ff3b30" }
const statusLabel = { green: "원활", yellow: "서행", red: "혼잡" }
const rankBadges = ["🥇 1위", "🥈 2위", "🥉 3위", "4위"]

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
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0 px-4 md:px-8 pt-6 max-w-3xl">
        <div className="flex items-center justify-between mb-1">
          <h1
            className="text-[#1a1a2e]"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: 26,
              letterSpacing: "-0.02em",
            }}
          >
            나의 즐겨찾기 경로
          </h1>
          <span
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
            style={{
              background: "rgba(0,122,255,0.1)",
              color: "#007aff",
              fontFamily: "var(--font-body)",
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#007aff] pulse-dot" />
            내 검색 횟수 상위 4개
          </span>
        </div>
        <p
          className="text-[#6b6b8a] text-sm mb-5"
          style={{ fontFamily: "var(--font-body)" }}
        >
          로그인한 계정에서 자주 검색한 경로만 안전하게 모아 보여드립니다.
        </p>

        {/* Favorite routes */}
        <div className="flex flex-col gap-3 mb-6">
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
                  className="glass p-5 cursor-pointer hover:scale-[1.01] transition-all border border-transparent hover:border-[#007aff]/30"
                  style={{ borderRadius: 22 }}
                  onClick={() =>
                    navigate(
                      `/route?origin=${encodeURIComponent(r.origin)}&dest=${encodeURIComponent(r.destination)}`
                    )
                  }
                  title="클릭 시 이 경로로 즉시 분석합니다"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div
                        className="w-11 h-11 flex items-center justify-center text-sm font-bold flex-shrink-0"
                        style={{
                          background: idx === 0 ? "linear-gradient(135deg, #ffd700, #ff9500)" : "rgba(240,242,248,0.9)",
                          color: idx === 0 ? "white" : "#4a4a68",
                          borderRadius: 14,
                          boxShadow: idx === 0 ? "0 4px 12px rgba(255,149,0,0.3)" : undefined,
                        }}
                      >
                        {idx + 1}위
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span
                            className="font-semibold text-[#1a1a2e] text-base truncate"
                            style={{ fontFamily: "var(--font-display)" }}
                          >
                            {r.label}
                          </span>
                          <span
                            className="text-xs px-2 py-0.5 rounded-full font-bold text-[#007aff] bg-blue-50 border border-blue-100 flex-shrink-0"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {r.search_count}회 검색
                          </span>
                          <span
                            className="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0"
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

                    <div className="text-right flex-shrink-0 pl-3">
                      <div className="flex items-end gap-1.5 justify-end">
                        <span
                          className="text-[#1a1a2e]"
                          style={{
                            fontFamily: "var(--font-display)",
                            fontWeight: 700,
                            fontSize: 28,
                            letterSpacing: "-0.02em",
                          }}
                        >
                          {r.currentTime}
                        </span>
                        <span className="text-sm text-[#6b6b8a] mb-1">분</span>
                      </div>
                      <p
                        className="text-xs font-medium"
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

          {/* New route search shortcut */}
          <button
            onClick={() => navigate("/route")}
            className="glass p-5 flex items-center gap-3 hover:bg-white/60 transition-colors text-left w-full cursor-pointer"
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
      </main>
    </div>
  )
}

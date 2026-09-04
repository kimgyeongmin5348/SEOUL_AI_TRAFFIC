import { useNavigate } from "react-router-dom"
import Sidebar from "../components/Sidebar"
import { favoriteRoutes } from "../data/mock"

const statusColor = { green: "#34c759", yellow: "#ff9500", red: "#ff3b30" }
const statusLabel = { green: "원활", yellow: "서행", red: "혼잡" }

export default function Favorites() {
  const navigate = useNavigate()

  return (
    <div className="min-h-full flex" style={{ background: "#eef0f5" }}>
      <Sidebar />
      <main className="flex-1 md:pl-20 pb-24 md:pb-0 px-4 md:px-8 pt-6 max-w-3xl">
        <h1
          className="text-[#1a1a2e] mb-1"
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: 26,
            letterSpacing: "-0.02em",
          }}
        >
          즐겨찾기
        </h1>
        <p
          className="text-[#6b6b8a] text-sm mb-5"
          style={{ fontFamily: "var(--font-body)" }}
        >
          자주 이용하는 경로 · 개인화 교통 정보
        </p>

        {/* Favorite routes */}
        <div className="flex flex-col gap-3 mb-6">
          {favoriteRoutes.map((r) => {
            const color = statusColor[(r.status as keyof typeof statusColor)]
            return (
              <div
                key={r.id}
                className="glass p-5 cursor-pointer hover:scale-[1.01] transition-transform"
                style={{ borderRadius: 22 }}
                onClick={() => navigate("/route")}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 flex items-center justify-center text-xl"
                      style={{
                        background: "rgba(240,242,248,0.9)",
                        borderRadius: 14,
                      }}
                    >
                      {r.label === "출근"
                        ? "🏢"
                        : r.label === "운동"
                          ? "💪"
                          : "🏠"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className="font-semibold text-[#1a1a2e]"
                          style={{
                            fontFamily: "var(--font-display)",
                            fontSize: 16,
                          }}
                        >
                          {r.label}
                        </span>
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{
                            background: `${color}15`,
                            color,
                            fontFamily: "var(--font-body)",
                          }}
                        >
                          {statusLabel[(r.status as keyof typeof statusLabel)]}
                        </span>
                      </div>
                      <p
                        className="text-xs text-[#6b6b8a] mt-0.5"
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {r.from} → {r.to}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
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
                      평소 대비 {r.delta > 0 ? `+${r.delta}분` : "정상"}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Add new */}
          <button
            className="glass p-5 flex items-center gap-3 hover:bg-white/50 transition-colors text-left w-full"
            style={{
              borderRadius: 22,
              border: "1.5px dashed rgba(0,122,255,0.3)",
            }}
          >
            <div
              className="w-10 h-10 flex items-center justify-center"
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
                경로 추가
              </p>
              <p
                className="text-xs text-[#6b6b8a]"
                style={{ fontFamily: "var(--font-body)" }}
              >
                자주 이용하는 경로를 저장하세요
              </p>
            </div>
          </button>
        </div>

        {/* Recent searches */}
        <div className="glass p-5" style={{ borderRadius: 22 }}>
          <h3
            className="text-[#1a1a2e] mb-4"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: 15,
            }}
          >
            최근 검색
          </h3>
          <div className="flex flex-col gap-1">
            {[
              {
                from: "마포구 합정동",
                to: "강남구 역삼동",
                time: "오늘 07:42",
              },
              {
                from: "강남구 역삼동",
                to: "서초구 방배동",
                time: "어제 19:15",
              },
              {
                from: "종로구 광화문",
                to: "영등포구 여의도",
                time: "어제 13:20",
              },
            ].map((s, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-3 px-2 -mx-2 hover:bg-white/40 rounded-xl cursor-pointer transition-colors"
                onClick={() => navigate("/route")}
              >
                <div className="flex items-center gap-3">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    className="text-[#b0b0c8] flex-shrink-0"
                  >
                    <circle
                      cx="8"
                      cy="8"
                      r="6"
                      stroke="currentColor"
                      strokeWidth="1.5"
                    />
                    <path
                      d="M8 5v3l2 1.5"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                  <div>
                    <p
                      className="text-sm text-[#1a1a2e]"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {s.from} → {s.to}
                    </p>
                    <p
                      className="text-xs text-[#b0b0c8]"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {s.time}
                    </p>
                  </div>
                </div>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  className="text-[#b0b0c8]"
                >
                  <path
                    d="M5 3l4 4-4 4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}

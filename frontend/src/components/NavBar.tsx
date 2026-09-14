import { useState, useEffect, useRef } from "react"
import { Link, useLocation } from "react-router-dom"
import { useAuth } from "../auth"

export default function NavBar() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const navRef = useRef<HTMLDivElement>(null)

  // Desktop primary navigation links
  const desktopLinks = [
    { href: "/", label: "서비스 소개" },
    { href: "/dashboard", label: "실시간 교통" },
    { href: "/prediction", label: "AI 예측" },
    { href: "/favorites", label: "즐겨찾기" },
  ]

  // Full mobile menu items with icons
  const mobileMenuItems = [
    {
      href: "/",
      label: "서비스 소개",
      desc: "RoadPulse 소개 및 핵심 기능",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M3 8.5L10 3l7 5.5V17a1 1 0 01-1 1H4a1 1 0 01-1-1V8.5z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path d="M7 18v-7h6v7" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ),
    },
    {
      href: "/dashboard",
      label: "실시간 교통 지도",
      desc: "서울시 실시간 도로 혼잡도",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M2 4.5L7 2l6 3 5-2.5v13L18 17l-5 2-6-3-5 2.5V4.5z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path d="M7 2v13M13 5v13" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ),
    },
    {
      href: "/route",
      label: "도로망 경로 분석",
      desc: "돌발·기상 반영 최적 경로",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 2C7.24 2 5 4.24 5 7c0 4 5 11 5 11s5-7 5-11c0-2.76-2.24-5-5-5z"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <circle cx="10" cy="7" r="2" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ),
    },
    {
      href: "/traffic",
      label: "도로별 속도 현황",
      desc: "주요 간선·도시고속도로 통계",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <rect
            x="6"
            y="2"
            width="8"
            height="16"
            rx="4"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <circle cx="10" cy="6" r="1.5" fill="currentColor" />
          <circle cx="10" cy="10" r="1.5" fill="currentColor" />
          <circle cx="10" cy="14" r="1.5" fill="currentColor" />
        </svg>
      ),
    },
    {
      href: "/incidents",
      label: "사고 및 통제 공사",
      desc: "실시간 돌발상황 알림",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 2.5L1.5 17.5h17L10 2.5z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path d="M10 8.5v4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <circle cx="10" cy="15" r="1" fill="currentColor" />
        </svg>
      ),
    },
    {
      href: "/weather",
      label: "기상 영향 분석",
      desc: "날씨와 도로 주행 속도",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M5 12a4 4 0 010-8 5.5 5.5 0 0110.5 2A3.5 3.5 0 0115 12H5z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path
            d="M7 15l-.5 2M10 15l-.5 2M13 15l-.5 2"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      ),
    },
    {
      href: "/prediction",
      label: "AI 미래 예측",
      desc: "딥러닝 기반 3시간 후 예측",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M2 16l4.5-5 3.5 3 4-6 4 4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="16" cy="4" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ),
    },
    {
      href: "/favorites",
      label: "나의 즐겨찾기",
      desc: "자주 가는 경로 저장 및 조회",
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 17s-7-4.5-7-9a4 4 0 018 0 4 4 0 018 0c0 4.5-7 9-7 9z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },
  ]

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [pathname])

  // Close on outside click or ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false)
    }
    const handleClickOutside = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setMobileMenuOpen(false)
      }
    }

    if (mobileMenuOpen) {
      document.addEventListener("keydown", handleKeyDown)
      document.addEventListener("mousedown", handleClickOutside)
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [mobileMenuOpen])

  return (
    <nav
      ref={navRef}
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-200"
      style={{
        paddingTop: "max(8px, env(safe-area-inset-top))",
        paddingLeft: "max(8px, env(safe-area-inset-left))",
        paddingRight: "max(8px, env(safe-area-inset-right))",
      }}
    >
      <div className="py-2 px-1 sm:px-4 max-w-6xl mx-auto">
        <div
          className="liquid-glass-nav flex items-center justify-between px-3.5 sm:px-5 py-2 sm:py-2.5 transition-all duration-300"
          style={{
            borderRadius: 24,
            boxShadow: "0 16px 40px rgba(0, 0, 0, 0.35), 0 1px 0 rgba(255, 255, 255, 0.25) inset",
          }}
        >
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2 group flex-shrink-0"
            onClick={() => setMobileMenuOpen(false)}
          >
            <div
              className="w-7 h-7 sm:w-8 sm:h-8 flex items-center justify-center transition-transform duration-200 group-hover:scale-105"
              style={{
                background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                borderRadius: 9,
                boxShadow: "0 2px 8px rgba(0,122,255,0.35)",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                <path
                  d="M2 9C2 5.13 5.13 2 9 2s7 3.13 7 7-3.13 7-7 7-7-3.13-7-7z"
                  stroke="white"
                  strokeWidth="1.6"
                />
                <path
                  d="M9 5v4l2.5 2.5"
                  stroke="white"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <circle cx="9" cy="9" r="1.2" fill="white" />
              </svg>
            </div>
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                letterSpacing: "-0.02em",
                textShadow: "0 2px 8px rgba(0,0,0,0.5)",
              }}
              className="text-white text-[16px] sm:text-[17px]"
            >
              RoadPulse
            </span>
          </Link>

          {/* Desktop Navigation Links */}
          <div className="hidden md:flex items-center gap-1 sm:gap-2">
            {desktopLinks.map((l) => {
              const active = pathname === l.href
              return (
                <Link
                  key={l.href}
                  to={l.href}
                  className={`px-3.5 py-1.5 text-xs sm:text-sm font-medium transition-all duration-200 rounded-xl ${
                    active
                      ? "text-white bg-white/[0.16] border border-white/[0.25]"
                      : "text-white/70 hover:text-white hover:bg-white/[0.08]"
                  }`}
                  style={{
                    fontFamily: "var(--font-body)",
                    textShadow: active
                      ? "0 0 10px rgba(0, 122, 255, 0.7), 0 1px 2px rgba(0, 0, 0, 0.5)"
                      : "0 1px 2px rgba(0, 0, 0, 0.4)",
                  }}
                >
                  {l.label}
                </Link>
              )
            })}
          </div>

          {/* Right Action Area */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Desktop Auth Button */}
            <div className="hidden sm:block">
              {user ? (
                <button
                  type="button"
                  onClick={() => void logout()}
                  title={user.email}
                  className="button-glide px-4 py-2 text-xs sm:text-sm font-semibold text-white transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
                  style={{
                    borderRadius: 14,
                    background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                    fontFamily: "var(--font-body)",
                    boxShadow: "0 4px 14px rgba(0, 122, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.35)",
                  }}
                >
                  <span>로그아웃</span>
                </button>
              ) : (
                <Link
                  to="/login"
                  className="button-glide px-4 py-2 text-xs sm:text-sm font-semibold text-white transition-all duration-200 inline-block cursor-pointer"
                  style={{
                    borderRadius: 14,
                    background: "linear-gradient(135deg, #007aff, #5e5ce6)",
                    fontFamily: "var(--font-body)",
                    boxShadow: "0 4px 14px rgba(0, 122, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.35)",
                  }}
                >
                  로그인
                </Link>
              )}
            </div>

            {/* Mobile Hamburger Toggle Button */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-label={mobileMenuOpen ? "메뉴 닫기" : "메뉴 열기"}
              aria-expanded={mobileMenuOpen}
              className="md:hidden flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-200 active:scale-90"
              style={{
                background: mobileMenuOpen ? "rgba(0,122,255,0.25)" : "rgba(255,255,255,0.12)",
                border: "1px solid rgba(255,255,255,0.25)",
                color: "#ffffff",
              }}
            >
              {mobileMenuOpen ? (
                // Close Icon (X)
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path
                    d="M4 4L14 14M14 4L4 14"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                // Hamburger Icon (3 lines)
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path
                    d="M3 4.5H15M3 9H15M3 13.5H15"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Panel */}
        {mobileMenuOpen && (
          <div
            className="md:hidden mt-2 p-3 rounded-3xl mobile-menu-animate overflow-hidden border border-white/25 shadow-2xl"
            style={{
              maxHeight: "calc(100dvh - 5.5rem)",
              background: "rgba(15, 23, 42, 0.92)",
              backdropFilter: "blur(28px) saturate(1.8)",
              WebkitBackdropFilter: "blur(28px) saturate(1.8)",
              boxShadow: "0 20px 50px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.2)",
            }}
          >
            {/* User status bar on mobile */}
            <div className="flex items-center justify-between px-3 py-2 mb-2 rounded-2xl bg-white/10 border border-white/15">
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0"
                  style={{ background: user ? "#34c759" : "#64748b" }}
                >
                  {user ? "✓" : "?"}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-white truncate">
                    {user ? user.email : "게스트 모드"}
                  </p>
                  <p className="text-[10px] text-white/60">
                    {user ? "즐겨찾기 자동 동기화 중" : "로그인 후 개인화 즐겨찾기 지원"}
                  </p>
                </div>
              </div>

              {user ? (
                <button
                  type="button"
                  onClick={() => {
                    void logout()
                    setMobileMenuOpen(false)
                  }}
                  className="px-2.5 py-1 text-xs font-medium text-red-400 rounded-lg hover:bg-red-500/20 transition-colors flex-shrink-0"
                >
                  로그아웃
                </button>
              ) : (
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-1 text-xs font-semibold text-white rounded-xl shadow-sm flex-shrink-0"
                  style={{ background: "linear-gradient(135deg, #007aff, #5e5ce6)" }}
                >
                  로그인
                </Link>
              )}
            </div>

            {/* Navigation links grid */}
            <div className="grid grid-cols-1 gap-1 max-h-[58dvh] overflow-y-auto pr-0.5">
              {mobileMenuItems.map((item) => {
                const active = pathname === item.href
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-2xl transition-all duration-150 active:scale-[0.99] ${
                      active ? "bg-white/15 text-white" : "text-white/80 hover:bg-white/10"
                    }`}
                  >
                    <div
                      className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform"
                      style={{
                        background: active ? "rgba(0, 122, 255, 0.35)" : "rgba(255, 255, 255, 0.08)",
                        color: active ? "#ffffff" : "rgba(255, 255, 255, 0.75)",
                      }}
                    >
                      {item.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold truncate text-white">
                          {item.label}
                        </span>
                        {active && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] shadow-[0_0_6px_#38bdf8]" />
                        )}
                      </div>
                      <p className="text-[11px] text-white/60 truncate">
                        {item.desc}
                      </p>
                    </div>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 16 16"
                      fill="none"
                      className={`flex-shrink-0 ${active ? "text-white" : "text-white/40"}`}
                    >
                      <path
                        d="M6 3l5 5-5 5"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </Link>
                )
              })}
            </div>

            {/* Bottom info banner */}
            <div className="mt-2 pt-2 border-t border-white/10 flex items-center justify-between px-2 text-[10px] text-white/50">
              <span>RoadPulse AI 교통망 서울 전역 지원</span>
              <span className="font-mono">v1.0 Mobile Ready</span>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}


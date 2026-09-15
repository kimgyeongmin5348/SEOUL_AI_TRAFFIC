import { useState, useEffect, useRef } from "react"
import { Link, useLocation } from "react-router-dom"
import { useAuth } from "../auth"
import BrandLogo from "./BrandLogo"

const navItems = [
  {
    href: "/dashboard",
    icon: (
      // 지도 아이콘
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M2 4.5L7 2l6 3 5-2.5v13L18 17l-5 2-6-3-5 2.5V4.5z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M7 2v13M13 5v13" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
    label: "지도",
  },
  {
    href: "/route",
    icon: (
      // 내비게이션 화살표 + 핀
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 2C7.24 2 5 4.24 5 7c0 4 5 11 5 11s5-7 5-11c0-2.76-2.24-5-5-5z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <circle cx="10" cy="7" r="2" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
    label: "경로",
  },
  {
    href: "/traffic",
    icon: (
      // 신호등
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect
          x="6"
          y="2"
          width="8"
          height="16"
          rx="4"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <circle cx="10" cy="6" r="1.5" fill="currentColor" />
        <circle cx="10" cy="10" r="1.5" fill="currentColor" />
        <circle cx="10" cy="14" r="1.5" fill="currentColor" />
      </svg>
    ),
    label: "교통량",
  },
  {
    href: "/incidents",
    icon: (
      // 경고 삼각형
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 2.5L1.5 17.5h17L10 2.5z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path
          d="M10 8.5v4.5"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="10" cy="15" r="1" fill="currentColor" />
      </svg>
    ),
    label: "사고/공사",
  },
  {
    href: "/weather",
    icon: (
      // 구름 + 빗방울
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M5 12a4 4 0 010-8 5.5 5.5 0 0110.5 2A3.5 3.5 0 0115 12H5z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path
          d="M7 15l-.5 2M10 15l-.5 2M13 15l-.5 2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
    label: "날씨",
  },
  {
    href: "/prediction",
    icon: (
      // 상승 그래프 + 별(AI)
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M2 16l4.5-5 3.5 3 4-6 4 4"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx="16"
          cy="4"
          r="2.5"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path
          d="M16 2.5v3M14.5 4h3"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinecap="round"
        />
      </svg>
    ),
    label: "AI 예측",
  },
  {
    href: "/favorites",
    icon: (
      // 하트
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 17s-7-4.5-7-9a4 4 0 018 0 4 4 0 018 0c0 4.5-7 9-7 9z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    ),
    label: "즐겨찾기",
  },
  {
    href: "/chatbot",
    icon: (
      // AI 챗봇 아이콘
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="3" y="5" width="14" height="11" rx="3" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="7.5" cy="10.5" r="1.2" fill="currentColor" />
        <circle cx="12.5" cy="10.5" r="1.2" fill="currentColor" />
        <path d="M10 2v3M3 10.5H1M19 10.5h-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M8 13.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
    label: "AI 챗봇",
  },
]

// 웹/데스크톱 사이드바에서는 AI 챗봇 제외 (모바일에서만 필요)
const desktopNavItems = navItems.filter((item) => item.href !== "/chatbot")

// 홈 전용 아이콘
const homeIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <path
      d="M3 8.5L10 3l7 5.5V17a1 1 0 01-1 1H4a1 1 0 01-1-1V8.5z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <path d="M7 18v-7h6v7" stroke="currentColor" strokeWidth="1.5" />
  </svg>
)

const chatbotIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <rect x="3" y="5" width="14" height="11" rx="3" stroke="currentColor" strokeWidth="1.5" />
    <circle cx="7.5" cy="10.5" r="1.2" fill="currentColor" />
    <circle cx="12.5" cy="10.5" r="1.2" fill="currentColor" />
    <path d="M10 2v3M3 10.5H1M19 10.5h-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M8 13.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
  </svg>
)

const mobileBottomNavItems = [
  { href: "/", label: "홈", icon: homeIcon },
  { href: "/dashboard", label: "지도", icon: navItems[0].icon },
  { href: "/route", label: "경로", icon: navItems[1].icon },
  { href: "/prediction", label: "예측", icon: navItems[5].icon },
  { href: "/favorites", label: "MY", icon: navItems[6].icon },
  { href: "/chatbot", label: "챗봇", icon: chatbotIcon },
]

export default function Sidebar() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Current page title lookup
  const currentPageItem = navItems.find((item) => item.href === pathname)
  const currentPageTitle = currentPageItem ? currentPageItem.label : "RoadPulse"

  // Close menu on route change
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [pathname])

  // Close on outside click or ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false)
    }
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
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
    <>
      {/* ======================================================== */}
      {/* 1. Mobile Top Bar (Only visible on screens < 768px)      */}
      {/* ======================================================== */}
      <header
        ref={menuRef}
        className="md:hidden fixed top-0 left-0 right-0 z-40"
        style={{
          paddingTop: "max(8px, env(safe-area-inset-top))",
          paddingLeft: "max(10px, env(safe-area-inset-left))",
          paddingRight: "max(10px, env(safe-area-inset-right))",
        }}
      >
        <div className="py-2 px-1 max-w-6xl mx-auto">
          <div
            className="glass flex items-center justify-between px-3.5 py-2.5"
            style={{
              borderRadius: 18,
              boxShadow: "0 8px 24px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
            }}
          >
            {/* Logo */}
            <Link
              to="/"
              className="flex items-center gap-2 group flex-shrink-0"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="RoadPulse 홈"
            >
              <BrandLogo className="w-[42px] h-7 rounded-lg transition-transform duration-300 group-hover:scale-105" />
              <span
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: 16,
                  letterSpacing: "-0.02em",
                }}
                className="text-[#1a1a2e]"
              >
                RoadPulse
              </span>
            </Link>

            {/* Current Page Badge */}
            <div className="hidden min-[420px]:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/[0.04] border border-black/[0.05]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#007aff] pulse-dot" />
              <span className="text-xs font-semibold text-[#3a3a52]">{currentPageTitle}</span>
            </div>

            {/* Right actions: User & Hamburger */}
            <div className="flex items-center gap-1.5">
              {user ? (
                <span
                  title={user.email}
                  className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[11px] font-bold"
                  style={{ background: "#34c759" }}
                >
                  ✓
                </span>
              ) : (
                <Link
                  to="/login"
                  className="px-2.5 py-1 text-xs font-semibold text-[#007aff] rounded-lg hover:bg-blue-50 transition-colors"
                >
                  로그인
                </Link>
              )}

              {/* Hamburger Button */}
              <button
                type="button"
                onClick={() => setMobileMenuOpen((prev) => !prev)}
                aria-label={mobileMenuOpen ? "전체 메뉴 닫기" : "전체 메뉴 열기"}
                aria-expanded={mobileMenuOpen}
                className="w-8 h-8 flex items-center justify-center rounded-xl transition-all duration-150 active:scale-90"
                style={{
                  background: mobileMenuOpen ? "rgba(0,122,255,0.12)" : "rgba(0,0,0,0.04)",
                  color: mobileMenuOpen ? "#007aff" : "#1a1a2e",
                }}
              >
                {mobileMenuOpen ? (
                  <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                    <path
                      d="M4 4L14 14M14 4L4 14"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
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

          {/* Mobile Full Menu Dropdown */}
          {mobileMenuOpen && (
            <div
              className="mt-2 glass p-3 rounded-3xl mobile-menu-animate overflow-hidden border border-white/80 shadow-2xl"
              style={{
                maxHeight: "calc(100dvh - 5.5rem)",
                background: "rgba(255, 255, 255, 0.9)",
                backdropFilter: "blur(28px) saturate(1.8)",
                WebkitBackdropFilter: "blur(28px) saturate(1.8)",
              }}
            >
              {/* User Bar */}
              <div className="flex items-center justify-between px-3 py-2 mb-2 rounded-2xl bg-white/60 border border-white/70">
                <div className="min-w-0 pr-2">
                  <p className="text-xs font-semibold text-[#1a1a2e] truncate">
                    {user ? user.email : "게스트 모드"}
                  </p>
                  <p className="text-[10px] text-[#6b6b8a]">
                    {user ? "개인화 즐겨찾기 동기화 완료" : "로그인 후 개인화 기능 이용 가능"}
                  </p>
                </div>
                {user ? (
                  <button
                    type="button"
                    onClick={() => {
                      void logout()
                      setMobileMenuOpen(false)
                    }}
                    className="px-2.5 py-1 text-xs font-medium text-red-600 rounded-lg hover:bg-red-50 flex-shrink-0"
                  >
                    로그아웃
                  </button>
                ) : (
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-3 py-1 text-xs font-semibold text-white rounded-xl flex-shrink-0"
                    style={{ background: "linear-gradient(135deg, #007aff, #5e5ce6)" }}
                  >
                    로그인
                  </Link>
                )}
              </div>

              {/* All Routes Grid */}
              <div className="grid grid-cols-1 gap-1 max-h-[58dvh] overflow-y-auto pr-0.5">
                <Link
                  to="/"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-2xl transition-all duration-150 ${
                    pathname === "/" ? "bg-[#007aff]/10 text-[#007aff]" : "text-[#2c2c44] hover:bg-white/60"
                  }`}
                >
                  <div
                    className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{
                      background: pathname === "/" ? "#007aff" : "rgba(0, 0, 0, 0.04)",
                      color: pathname === "/" ? "#ffffff" : "#4a4a68",
                    }}
                  >
                    {homeIcon}
                  </div>
                  <span className="text-sm font-semibold">서비스 소개</span>
                </Link>

                {navItems.map((item) => {
                  const active = pathname === item.href
                  return (
                    <Link
                      key={item.href}
                      to={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center gap-3 px-3 py-2 rounded-2xl transition-all duration-150 ${
                        active ? "bg-[#007aff]/10 text-[#007aff]" : "text-[#2c2c44] hover:bg-white/60"
                      }`}
                    >
                      <div
                        className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0"
                        style={{
                          background: active ? "#007aff" : "rgba(0, 0, 0, 0.04)",
                          color: active ? "#ffffff" : "#4a4a68",
                        }}
                      >
                        {item.icon}
                      </div>
                      <span className="text-sm font-semibold">{item.label}</span>
                      {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[#007aff]" />}
                    </Link>
                  )
                })}
              </div>

              <div className="mt-2 pt-2 border-t border-black/5 flex items-center justify-between px-2 text-[10px] text-[#8e8e93]">
                <span>서울시 AI 교통 관제</span>
                <span className="font-mono">Mobile Optimized</span>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* ======================================================== */}
      {/* 2. Desktop Sidebar (Screens >= 768px)                     */}
      {/* ======================================================== */}
      <aside
        className="liquid-glass-nav sidebar-floating hidden md:flex flex-col w-[78px] fixed left-4 top-1/2 z-50 py-3 gap-1"
        style={{ borderRadius: 28 }}
      >
        <Link to="/" className="flex justify-center mb-3 group" title="홈으로 이동">
          <BrandLogo className="w-[52px] h-[35px] rounded-lg transition-transform duration-300 group-hover:scale-110" />
        </Link>

        {/* Nav items container with sliding indicator */}
        <div className="relative flex flex-col gap-1 w-full px-1">
          {(() => {
            const activeIndex = desktopNavItems.findIndex((item) => item.href === pathname)
            return (
              <>
                {/* Fluid Sliding Active Indicator Pill */}
                {activeIndex !== -1 && (
                  <div
                    className="sidebar-desktop-active-indicator"
                    style={{
                      transform: `translateY(${activeIndex * 56}px)`,
                    }}
                  />
                )}

                {desktopNavItems.map((item, idx) => {
                  const active = activeIndex === idx
                  return (
                    <Link
                      key={item.href}
                      to={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`sidebar-liquid-link relative z-10 flex flex-col items-center justify-center h-[52px] w-full ${
                        active ? "is-active" : ""
                      }`}
                      style={{ borderRadius: 16 }}
                    >
                      <div
                        className="transition-all duration-300"
                        style={{
                          color: active ? "#ffffff" : "rgba(255, 255, 255, 0.75)",
                          filter: active
                            ? "drop-shadow(0 0 8px rgba(0, 122, 255, 0.8)) drop-shadow(0 0 14px rgba(94, 92, 230, 0.5))"
                            : "drop-shadow(0 1px 2px rgba(0,0,0,0.5))",
                          transform: active ? "scale(1.1)" : "scale(1)",
                        }}
                      >
                        {item.icon}
                      </div>
                      <span
                        className="transition-all duration-300"
                        style={{
                          fontSize: 10,
                          fontFamily: "var(--font-body)",
                          fontWeight: active ? 700 : 500,
                          lineHeight: 1,
                          letterSpacing: "-0.01em",
                          color: active ? "#ffffff" : "rgba(255, 255, 255, 0.75)",
                          textShadow: active
                            ? "0 0 10px rgba(0, 122, 255, 0.9), 0 1px 3px rgba(0, 0, 0, 0.6)"
                            : "0 1px 3px rgba(0, 0, 0, 0.6)",
                        }}
                      >
                        {item.label}
                      </span>
                    </Link>
                  )
                })}
              </>
            )
          })()}
        </div>
      </aside>

      {/* ======================================================== */}
      {/* 3. Mobile Bottom Nav Bar (Screens < 768px)               */}
      {/* ======================================================== */}
      <nav
        className="md:hidden fixed bottom-1.5 left-2 right-2 sm:left-3 sm:right-3 z-50 liquid-glass-nav flex items-center px-0.5 sm:px-1"
        style={{
          borderRadius: 22,
          paddingTop: 5,
          paddingBottom: "max(10px, env(safe-area-inset-bottom))",
        }}
      >
        {(() => {
          const mobileIndex = mobileBottomNavItems.findIndex((item) => item.href === pathname)

          return (
            <div className="relative grid grid-cols-6 items-center w-full">
              {/* Fluid Mobile Horizontal Sliding Active Indicator */}
              {mobileIndex !== -1 && (
                <div
                  className="sidebar-mobile-active-indicator"
                  style={{
                    width: "16.666%",
                    transform: `translateX(${mobileIndex * 100}%)`,
                  }}
                >
                  <div
                    className="mx-0.5 sm:mx-1 h-[44px] rounded-xl"
                    style={{
                      background: "rgba(255, 255, 255, 0.18)",
                      border: "1px solid rgba(255, 255, 255, 0.38)",
                      boxShadow:
                        "0 4px 14px rgba(0,0,0,0.15), 0 0 12px rgba(0,122,255,0.28), inset 0 1px 0 rgba(255,255,255,0.4)",
                      backdropFilter: "blur(10px)",
                      WebkitBackdropFilter: "blur(10px)",
                    }}
                  />
                </div>
              )}

              {mobileBottomNavItems.map((item, idx) => {
                const active = mobileIndex === idx
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    aria-current={active ? "page" : undefined}
                    className="sidebar-liquid-link relative z-10 flex flex-col items-center justify-center h-[44px] px-0.5"
                  >
                    <div
                      className="transition-all duration-300 scale-90 sm:scale-100"
                      style={{
                        color: active ? "#ffffff" : "rgba(255, 255, 255, 0.75)",
                        filter: active
                          ? "drop-shadow(0 0 6px rgba(0, 122, 255, 0.8))"
                          : "drop-shadow(0 1px 2px rgba(0,0,0,0.5))",
                        transform: active ? "scale(1.05)" : "scale(1)",
                      }}
                    >
                      {item.icon}
                    </div>
                    <span
                      className="transition-all duration-300 text-[9px] sm:text-[10px] tracking-tight leading-tight mt-0.5 truncate"
                      style={{
                        fontWeight: active ? 700 : 500,
                        color: active ? "#ffffff" : "rgba(255, 255, 255, 0.75)",
                        textShadow: active
                          ? "0 0 8px rgba(0, 122, 255, 0.9), 0 1px 2px rgba(0, 0, 0, 0.6)"
                          : "0 1px 2px rgba(0, 0, 0, 0.6)",
                      }}
                    >
                      {item.label}
                    </span>
                  </Link>
                )
              })}
            </div>
          )
        })()}
      </nav>
    </>
  )
}

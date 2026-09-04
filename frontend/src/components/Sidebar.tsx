import { Link, useLocation } from "react-router-dom"

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
      // 경고 삼각형 (더 두껍고 명확하게)
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
      // 하트 + 경로
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
]

const mobileNavItems = [
  { href: "/", label: "홈", icon: navItems[0].icon },
  { href: "/dashboard", label: "지도", icon: navItems[0].icon },
  { href: "/route", label: "경로", icon: navItems[1].icon },
  { href: "/prediction", label: "예측", icon: navItems[5].icon },
  { href: "/favorites", label: "MY", icon: navItems[6].icon },
]

export default function Sidebar() {
  const { pathname } = useLocation()

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className="glass hidden md:flex flex-col w-[72px] fixed left-3 top-1/2 -translate-y-1/2 z-40 py-3 gap-0.5"
        style={{ borderRadius: 22 }}
      >
        <Link to="/" className="flex justify-center mb-3">
          <div
            className="w-8 h-8 flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #007aff, #5e5ce6)",
              borderRadius: 10,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M2 9C2 5.13 5.13 2 9 2s7 3.13 7 7-3.13 7-7 7-7-3.13-7-7z"
                stroke="white"
                strokeWidth="1.5"
              />
              <circle cx="9" cy="9" r="1.5" fill="white" />
            </svg>
          </div>
        </Link>

        {navItems.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              to={item.href}
              className="flex flex-col items-center gap-1 py-2 px-1 mx-1 transition-all duration-200 hover:scale-105"
              style={{
                borderRadius: 14,
                color: active ? "#007aff" : "#6b6b8a",
                background: active ? "rgba(0,122,255,0.1)" : "transparent",
              }}
            >
              {item.icon}
              <span
                style={{
                  fontSize: 9,
                  fontFamily: "var(--font-body)",
                  fontWeight: active ? 600 : 400,
                  lineHeight: 1,
                  letterSpacing: "-0.01em",
                }}
              >
                {item.label}
              </span>
            </Link>
          )
        })}
      </aside>

      {/* Mobile bottom nav */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-50 glass flex justify-around items-center px-2"
        style={{
          borderRadius: "24px 24px 0 0",
          paddingTop: 12,
          paddingBottom: "max(12px, env(safe-area-inset-bottom))",
        }}
      >
        {mobileNavItems.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              to={item.href}
              className="flex flex-col items-center gap-1 px-2"
              style={{ color: active ? "#007aff" : "#6b6b8a" }}
            >
              {item.icon}
              <span style={{ fontSize: 10, fontWeight: active ? 600 : 400 }}>
                {item.label}
              </span>
            </Link>
          )
        })}
      </nav>
    </>
  )
}

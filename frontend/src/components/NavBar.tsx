import { Link, useLocation } from "react-router-dom"

export default function NavBar() {
  const { pathname } = useLocation()

  const links = [
    { href: "/", label: "서비스 소개" },
    { href: "/dashboard", label: "실시간 교통" },
    { href: "/prediction", label: "AI 예측" },
    { href: "/favorites", label: "즐겨찾기" },
  ]

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 px-6"
      style={{
        paddingTop: "env(safe-area-inset-top)",
      }}
    >
      <div className="py-3">
        <div
          className="glass mx-auto max-w-6xl flex items-center justify-between px-5 py-3"
          style={{ borderRadius: 20 }}
        >
          <Link to="/" className="flex items-center gap-2.5">
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
                <path
                  d="M9 5v4l2.5 2.5"
                  stroke="white"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <circle cx="9" cy="9" r="1" fill="white" />
              </svg>
            </div>
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 17,
                letterSpacing: "-0.02em",
              }}
              className="text-[#1a1a2e]"
            >
              RoadPulse
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                to={l.href}
                className="px-4 py-2 text-sm font-medium transition-all duration-200"
                style={{
                  borderRadius: 12,
                  color: pathname === l.href ? "#007aff" : "#4a4a68",
                  background:
                    pathname === l.href ? "rgba(0,122,255,0.1)" : "transparent",
                  fontFamily: "var(--font-body)",
                }}
              >
                {l.label}
              </Link>
            ))}
          </div>

          <Link
            to="/login"
            className="px-4 py-2 text-sm font-semibold text-white transition-all duration-200 hover:opacity-90 active:scale-95"
            style={{
              borderRadius: 12,
              background: "linear-gradient(135deg, #007aff, #5e5ce6)",
              fontFamily: "var(--font-body)",
            }}
          >
            로그인
          </Link>
        </div>
      </div>
    </nav>
  )
}

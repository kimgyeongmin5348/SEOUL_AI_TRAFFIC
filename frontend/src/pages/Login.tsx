import { useState } from "react"
import { useNavigate } from "react-router-dom"

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [pw, setPw] = useState("")

  return (
    <div
      className="min-h-full flex items-center justify-center px-6"
      style={{
        background: "linear-gradient(160deg, #e8edf5 0%, #dce3f0 100%)",
      }}
    >
      {/* BG abstract */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none opacity-20">
        <svg
          viewBox="0 0 800 600"
          className="w-full h-full"
          preserveAspectRatio="xMidYMid slice"
        >
          {[80, 240, 400, 560, 720].map((x) => (
            <line
              key={x}
              x1={x}
              y1={0}
              x2={x + 10}
              y2={600}
              stroke="#007aff"
              strokeWidth="1"
            />
          ))}
          {[80, 200, 320, 440].map((y) => (
            <line
              key={y}
              x1={0}
              y1={y}
              x2={800}
              y2={y + 5}
              stroke="#5e5ce6"
              strokeWidth="1"
            />
          ))}
        </svg>
      </div>

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="w-14 h-14 mx-auto mb-4 flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #007aff, #5e5ce6)",
              borderRadius: 18,
              boxShadow: "0 8px 32px rgba(0,122,255,0.4)",
            }}
          >
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <circle cx="14" cy="14" r="10" stroke="white" strokeWidth="1.8" />
              <circle cx="14" cy="14" r="3" fill="white" />
              <path
                d="M14 7v3M14 18v3M7 14h3M18 14h3"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <h1
            className="text-[#1a1a2e]"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: 28,
              letterSpacing: "-0.02em",
            }}
          >
            RoadPulse
          </h1>
          <p
            className="text-[#6b6b8a] text-sm mt-1"
            style={{ fontFamily: "var(--font-body)" }}
          >
            도시의 흐름을 읽다
          </p>
        </div>

        <div className="glass p-7" style={{ borderRadius: 28 }}>
          <h2
            className="text-[#1a1a2e] mb-5"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: 20,
            }}
          >
            로그인
          </h2>

          <div className="flex flex-col gap-3">
            <div>
              <label
                className="block text-xs font-medium text-[#4a4a68] mb-1.5"
                style={{ fontFamily: "var(--font-body)" }}
              >
                이메일
              </label>
              <input
                type="email"
                className="w-full px-4 py-3 text-sm outline-none"
                style={{
                  background: "rgba(240,242,248,0.9)",
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.9)",
                  fontFamily: "var(--font-body)",
                  color: "#1a1a2e",
                }}
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label
                className="block text-xs font-medium text-[#4a4a68] mb-1.5"
                style={{ fontFamily: "var(--font-body)" }}
              >
                비밀번호
              </label>
              <input
                type="password"
                className="w-full px-4 py-3 text-sm outline-none"
                style={{
                  background: "rgba(240,242,248,0.9)",
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.9)",
                  fontFamily: "var(--font-body)",
                  color: "#1a1a2e",
                }}
                placeholder="비밀번호 입력"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
              />
            </div>

            <button
              onClick={() => navigate("/dashboard")}
              className="w-full py-3.5 font-semibold text-white mt-1 transition-all hover:opacity-90 active:scale-98"
              style={{
                borderRadius: 18,
                background: "linear-gradient(135deg, #007aff 0%, #5e5ce6 100%)",
                fontFamily: "var(--font-display)",
                fontSize: 15,
                letterSpacing: "-0.01em",
              }}
            >
              로그인
            </button>

            <div className="flex items-center gap-3 my-1">
              <div className="flex-1 h-px bg-black/8" />
              <span
                className="text-xs text-[#b0b0c8]"
                style={{ fontFamily: "var(--font-body)" }}
              >
                또는
              </span>
              <div className="flex-1 h-px bg-black/8" />
            </div>

            <button
              onClick={() => navigate("/dashboard")}
              className="w-full py-3 text-sm font-medium transition-all hover:bg-black/5"
              style={{
                borderRadius: 16,
                background: "rgba(240,242,248,0.9)",
                border: "1px solid rgba(255,255,255,0.9)",
                color: "#4a4a68",
                fontFamily: "var(--font-body)",
              }}
            >
              비회원으로 계속하기
            </button>
          </div>

          <p
            className="text-center text-xs text-[#b0b0c8] mt-5"
            style={{ fontFamily: "var(--font-body)" }}
          >
            계정이 없으신가요?{" "}
            <button className="text-[#007aff] font-medium">회원가입</button>
          </p>
        </div>
      </div>
    </div>
  )
}

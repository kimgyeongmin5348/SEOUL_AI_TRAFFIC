import { useState, useRef, useEffect } from "react"
import Sidebar from "../components/Sidebar"
import SubpageBackground from "../components/SubpageBackground"
import ChatMessageContent from "../components/ChatMessageContent"
import { sendChatMessage, ChatMessage } from "../services/api"

const SUGGESTIONS = [
  "지금 올림픽대로 정체 심한가요?",
  "비 올 때 운전 주의구간과 우회 팁",
  "강남에서 여의도 갈 때 빠른 경로 추천",
  "RoadPulse 경로 분석 기능이 뭐야?",
]

export default function ChatbotPage() {
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "안녕하세요! 서울 실시간 교통 AI 비서 RoadPulse입니다. 🚗\n출퇴근 정체 구간, 도로 상황, 우회로 등 교통에 대해 무엇이든 물어보세요!",
    },
  ])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim()
    if (!text || loading) return

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: text }]
    setMessages(newMessages)
    setInput("")
    setLoading(true)

    try {
      const payload = newMessages.slice(-8).map((m) => ({ role: m.role, content: m.content }))
      const res = await sendChatMessage(payload)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          thinking: res.thinking,
          grounding: res.grounding,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "일시적인 네트워크 오류로 답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleReset = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "대화가 새로 시작되었습니다. 서울 교통에 대해 무엇이든 편하게 물어보세요!",
      },
    ])
  }

  return (
    <div className="relative min-h-screen text-white bg-[#0c1424] flex flex-col md:flex-row overflow-hidden">
      <SubpageBackground />
      <Sidebar />

      {/* Main Container */}
      <main className="flex-1 flex flex-col h-screen max-h-screen relative z-10 md:pl-20 pt-16 md:pt-0">
        {/* Top Bar */}
        <header className="px-4 py-3.5 border-b border-white/10 bg-[#0c1424]/80 backdrop-blur-md flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(56,189,248,0.4)]">
              <span className="text-xl leading-none">🤖</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-tight">RoadPulse 교통 AI 챗봇</h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Thinking
                </span>
              </div>
              <p className="text-xs text-slate-400">실시간 서울 교통 분석 & 지능형 경로 가이드</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
              <path d="M3 21v-5h5" />
            </svg>
            <span>새 대화</span>
          </button>
        </header>

        {/* Chat History Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scrollbar-thin scrollbar-thumb-white/10 max-w-4xl w-full mx-auto">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              {m.role === "assistant" && m.thinking && (
                <details className="mb-2 w-full max-w-2xl rounded-xl bg-slate-900/90 border border-cyan-500/30 p-3 text-left shadow-sm">
                  <summary className="cursor-pointer text-xs font-semibold text-cyan-400 flex items-center gap-1.5 select-none hover:text-cyan-300">
                    <span>🧠</span> AI 사고 과정 (Thinking Process)
                  </summary>
                  <div className="mt-2.5 pl-2.5 border-l-2 border-cyan-500/40 text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {m.thinking}
                  </div>
                </details>
              )}
              <div
                className={`px-4 py-3 rounded-2xl max-w-[92%] md:max-w-2xl min-w-0 overflow-hidden ${
                  m.role === "user"
                    ? "bg-blue-600 text-white rounded-br-none shadow-md text-sm leading-relaxed whitespace-pre-wrap"
                    : "bg-slate-800/90 text-slate-100 rounded-bl-none border border-white/10 shadow-sm"
                }`}
              >
                {m.role === "assistant" ? (
                  <ChatMessageContent content={m.content} grounding={m.grounding} />
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex flex-col items-start gap-1">
              <div className="px-4 py-3 rounded-2xl bg-slate-800/90 border border-white/10 text-xs text-cyan-300 flex items-center gap-2.5">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                <span>교통 상황 및 도로 네트워크를 분석·추론하는 중입니다...</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Bottom Input Area (with mobile safe padding for bottom nav) */}
        <div className="p-3 md:p-4 bg-[#0c1424]/90 backdrop-blur-xl border-t border-white/10 pb-20 md:pb-4">
          <div className="max-w-4xl w-full mx-auto flex flex-col gap-2">
            {/* Quick Question Chips */}
            {messages.length <= 2 && (
              <div className="flex flex-wrap gap-1.5 pb-1">
                {SUGGESTIONS.map((q, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSend(q)}
                    className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Input Bar */}
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="서울 도로 교통 상황이나 우회 경로를 물어보세요..."
                className="flex-1 bg-white/5 border border-white/15 rounded-2xl px-4 py-3 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-cyan-400 transition-colors"
              />
              <button
                type="button"
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className="px-4 py-3 rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white flex items-center justify-center font-medium text-sm transition-colors shadow-sm"
              >
                <span className="hidden sm:inline mr-1.5">보내기</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

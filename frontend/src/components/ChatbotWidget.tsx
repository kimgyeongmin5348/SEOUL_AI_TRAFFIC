import { useState, useRef, useEffect } from "react"
import { sendChatMessage, ChatMessage } from "../services/api"
import ChatMessageContent from "./ChatMessageContent"

const SUGGESTIONS = [
  "지금 올림픽대로 정체 심한가요?",
  "비 올 때 운전 주의구간과 우회 팁",
  "강남에서 여의도 갈 때 빠른 경로 추천",
  "RoadPulse AI 예측 기능이 뭐야?",
]

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "안녕하세요! 서울 실시간 교통 AI 비서 RoadPulse입니다. 🚗\n도로 상황, 정체 구간, 우회 경로 등 궁금한 점을 편하게 물어보세요!",
    },
  ])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isOpen, messages, loading])

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim()
    if (!text || loading) return

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: text }]
    setMessages(newMessages)
    setInput("")
    setLoading(true)

    try {
      // Send conversation history (last 8 messages)
      const payload = newMessages.slice(-8).map((m) => ({ role: m.role, content: m.content }))
      const res = await sendChatMessage(payload)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          thinking: res.thinking,
        },
      ])
    } catch (err) {
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
          "대화가 새로 시작되었습니다. 서울 교통에 대해 무엇이든 물어보세요!",
      },
    ])
  }

  return (
    <aside aria-label="RoadPulse AI 챗봇" className="hidden md:block fixed bottom-6 left-6 z-50 select-none">
      {/* 1. Chat Popup Window */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="AI 챗봇 대화창"
          className="mb-3 w-[390px] h-[550px] max-h-[80vh] flex flex-col rounded-2xl bg-[#0c1424]/95 backdrop-blur-2xl border border-white/15 shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden transition-all duration-300 animate-in fade-in slide-in-from-bottom-5"
          style={{ textShadow: "none" }}
        >
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-blue-900/60 to-indigo-900/50 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-sm">
                <span className="text-base leading-none">🤖</span>
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-bold text-white tracking-tight">RoadPulse 교통 AI</h3>
                  <span className="px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    Thinking
                  </span>
                </div>
                <p className="text-[10px] text-slate-400">서울시 실시간 교통 & AI 예측</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleReset}
                title="새 대화 시작"
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
                  <path d="M21 3v5h-5" />
                  <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                  <path d="M3 21v-5h5" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="닫기"
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Message List */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3 scrollbar-thin scrollbar-thumb-white/10">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                {m.role === "assistant" && m.thinking && (
                  <details className="mb-1.5 w-full max-w-[92%] rounded-lg bg-slate-900/80 border border-cyan-500/25 p-2 text-left">
                    <summary className="cursor-pointer text-[11px] font-semibold text-cyan-400 flex items-center gap-1 select-none hover:text-cyan-300">
                      <span>🧠</span> AI 사고 과정 (Thinking Process)
                    </summary>
                    <div className="mt-2 pl-2 border-l border-cyan-500/30 text-[10px] font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-36 overflow-y-auto">
                      {m.thinking}
                    </div>
                  </details>
                )}
                <div
                  className={`px-3.5 py-2.5 rounded-2xl max-w-[92%] min-w-0 overflow-hidden ${
                    m.role === "user"
                      ? "bg-blue-600 text-white rounded-br-none shadow-md text-xs leading-relaxed whitespace-pre-wrap"
                      : "bg-slate-800/80 text-slate-100 rounded-bl-none border border-white/10"
                  }`}
                >
                  {m.role === "assistant" ? (
                    <ChatMessageContent content={m.content} compact />
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex flex-col items-start gap-1">
                <div className="px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-[11px] text-cyan-300 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  <span>교통 상황 및 경로를 추론하는 중...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Quick Suggestions (if only 1 or 2 messages) */}
          {messages.length <= 2 && (
            <div className="px-3 py-1.5 border-t border-white/5 bg-slate-900/40 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((q, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSend(q)}
                  className="px-2 py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] text-slate-300 text-left transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {/* Input Box */}
          <div className="p-2.5 bg-slate-900/90 border-t border-white/10 flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="서울 도로 교통 상황을 물어보세요..."
              className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-cyan-400 transition-colors"
            />
            <button
              type="button"
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              className="w-8 h-8 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white flex items-center justify-center transition-colors shadow-sm"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* 2. Floating Circular Character Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-label="AI 챗봇 열기"
        className="group relative flex items-center justify-center w-14 h-14 rounded-full bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 text-white shadow-[0_8px_25px_rgba(0,112,243,0.45),0_0_15px_rgba(56,189,248,0.4)] hover:scale-105 active:scale-95 transition-all duration-300"
      >
        {/* Animated halo ring */}
        <span className="absolute -inset-1 rounded-full bg-cyan-400/20 blur-sm group-hover:bg-cyan-400/40 transition-colors pointer-events-none" />

        {/* Robot Character Icon */}
        <div className="relative z-10 flex flex-col items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 36 36" fill="none">
            {/* Robot Head */}
            <rect x="7" y="10" width="22" height="18" rx="6" fill="#0c1424" stroke="#ffffff" strokeWidth="2" />
            {/* Antenna */}
            <line x1="18" y1="4" x2="18" y2="10" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
            <circle cx="18" cy="3" r="2" fill="#38bdf8" />
            {/* Robot Eyes with glow */}
            <circle cx="13.5" cy="18" r="2.5" fill="#38bdf8" />
            <circle cx="22.5" cy="18" r="2.5" fill="#38bdf8" />
            {/* Robot Mouth / Smile */}
            <path d="M14 23c1.2 1.2 2.8 1.5 4 1.5s2.8-.3 4-1.5" stroke="#38bdf8" strokeWidth="1.6" strokeLinecap="round" />
            {/* Ear knobs */}
            <rect x="4" y="15" width="3" height="8" rx="1.5" fill="#38bdf8" />
            <rect x="29" y="15" width="3" height="8" rx="1.5" fill="#38bdf8" />
          </svg>
        </div>

        {/* Online Status Dot */}
        <span className="absolute top-1 right-1 flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-400 border-2 border-[#0c1424]" />
        </span>

        {/* Tooltip on hover */}
        {!isOpen && (
          <span className="absolute left-16 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-white/10 text-white text-[11px] font-medium whitespace-nowrap shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            AI 챗봇과 대화하기
          </span>
        )}
      </button>
    </aside>
  )
}

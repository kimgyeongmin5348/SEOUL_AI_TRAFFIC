import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { ChatGrounding } from "../services/api"

interface ChatMessageContentProps {
  content: string
  compact?: boolean
  grounding?: ChatGrounding
}

export default function ChatMessageContent({
  content,
  compact = false,
  grounding,
}: ChatMessageContentProps) {
  return (
    <div className="min-w-0">
      <div
        className={`min-w-0 overflow-x-auto break-words text-left ${
          compact ? "text-xs leading-[1.7]" : "text-sm leading-7"
        }`}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-base font-bold text-white first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-4 text-[0.95rem] font-bold text-cyan-100 first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1.5 mt-3 font-semibold text-cyan-100 first:mt-0">{children}</h3>
          ),
          p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
          ul: ({ children }) => (
            <ul className="my-2 list-disc space-y-1 pl-5 marker:text-cyan-400">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 list-decimal space-y-1 pl-5 marker:font-semibold marker:text-cyan-400">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 rounded-r-lg border-l-3 border-cyan-400 bg-cyan-400/10 px-3 py-1 text-slate-200">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <table className="my-3 w-full min-w-[300px] border-collapse overflow-hidden rounded-lg text-left text-[0.92em]">
              {children}
            </table>
          ),
          thead: ({ children }) => <thead className="bg-cyan-500/15 text-cyan-100">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-white/10">{children}</tbody>,
          th: ({ children }) => (
            <th className="border border-white/15 px-2.5 py-2 font-semibold whitespace-nowrap">{children}</th>
          ),
          td: ({ children }) => <td className="border border-white/10 px-2.5 py-2 align-top">{children}</td>,
          hr: () => <hr className="my-4 border-white/15" />,
          code: ({ children }) => (
            <code className="rounded bg-slate-950/70 px-1.5 py-0.5 font-mono text-[0.9em] text-cyan-200">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-lg border border-white/10 bg-slate-950/80 p-3 text-xs leading-relaxed">
              {children}
            </pre>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="font-medium text-cyan-300 underline decoration-cyan-400/50 underline-offset-2 hover:text-cyan-200"
            >
              {children}
            </a>
          ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>

      {grounding && (
        <div className="mt-3 border-t border-white/10 pt-2.5 text-[10px] leading-relaxed text-slate-400">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`rounded-full border px-2 py-0.5 font-semibold ${
                grounding.grounded
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                  : "border-amber-400/30 bg-amber-400/10 text-amber-300"
              }`}
            >
              {grounding.grounded ? "RoadPulse 데이터 기반" : "근거 데이터 제한"}
            </span>
            {grounding.sources.map((source) => (
              <span key={source} className="rounded-full bg-white/5 px-2 py-0.5 text-slate-300">
                {source}
              </span>
            ))}
          </div>
          {grounding.queried_at && (
            <p className="mt-1.5">조회 기준 {new Date(grounding.queried_at).toLocaleString("ko-KR")}</p>
          )}
          {!!grounding.warnings?.length && (
            <p className="mt-1 text-amber-300/90">일부 제한: {grounding.warnings.join(" · ")}</p>
          )}
        </div>
      )}
    </div>
  )
}

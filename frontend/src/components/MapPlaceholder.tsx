interface MapProps {
  height?: number | string
}

const roads = [
  // Horizontal major roads
  {
    x1: 0,
    y1: 180,
    x2: 800,
    y2: 165,
    color: "#ff3b30",
    width: 4,
    label: "강변북로",
  },
  {
    x1: 0,
    y1: 320,
    x2: 800,
    y2: 310,
    color: "#ff9500",
    width: 3.5,
    label: "올림픽대로",
  },
  {
    x1: 0,
    y1: 240,
    x2: 800,
    y2: 235,
    color: "#ff9500",
    width: 3,
    label: "내부순환로",
  },
  // Vertical major roads
  {
    x1: 160,
    y1: 0,
    x2: 155,
    y2: 480,
    color: "#34c759",
    width: 3,
    label: "서부간선",
  },
  {
    x1: 380,
    y1: 0,
    x2: 375,
    y2: 480,
    color: "#34c759",
    width: 3.5,
    label: "경부고속",
  },
  {
    x1: 600,
    y1: 0,
    x2: 595,
    y2: 480,
    color: "#ff9500",
    width: 3,
    label: "동부간선",
  },
  // Secondary roads
  { x1: 0, y1: 110, x2: 500, y2: 100, color: "#34c759", width: 2, label: "" },
  { x1: 300, y1: 0, x2: 295, y2: 480, color: "#34c759", width: 2, label: "" },
  { x1: 500, y1: 0, x2: 495, y2: 480, color: "#34c759", width: 2, label: "" },
  { x1: 0, y1: 380, x2: 800, y2: 375, color: "#34c759", width: 2, label: "" },
  { x1: 0, y1: 420, x2: 800, y2: 415, color: "#34c759", width: 2, label: "" },
  { x1: 70, y1: 0, x2: 65, y2: 480, color: "#34c759", width: 2, label: "" },
  { x1: 700, y1: 0, x2: 695, y2: 480, color: "#34c759", width: 2, label: "" },
  // Diagonal / curve-ish roads
  { x1: 0, y1: 60, x2: 400, y2: 140, color: "#34c759", width: 1.5, label: "" },
  {
    x1: 400,
    y1: 440,
    x2: 800,
    y2: 360,
    color: "#34c759",
    width: 1.5,
    label: "",
  },
]

const spots = [
  { cx: 160, cy: 180, r: 5, color: "#ff3b30" },
  { cx: 375, cy: 310, r: 5, color: "#ff9500" },
  { cx: 595, cy: 235, r: 4, color: "#34c759" },
  { cx: 380, cy: 175, r: 6, color: "#ff3b30", pulse: true },
  { cx: 155, cy: 320, r: 5, color: "#ff9500" },
]

const aiZones = [
  { x: 290, y: 150, width: 100, height: 80 },
  { x: 550, y: 290, width: 80, height: 60 },
]

export default function MapPlaceholder({ height = 480 }: MapProps) {
  return (
    <div
      className="relative overflow-hidden w-full"
      style={{
        height,
        background: "linear-gradient(160deg, #e8edf5 0%, #dde4f0 100%)",
      }}
    >
      <svg
        viewBox="0 0 800 480"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 w-full h-full opacity-90"
      >
        {/* Background city blocks */}
        {Array.from({ length: 18 }).map((_, i) =>
          Array.from({ length: 12 }).map((_, j) => (
            <rect
              key={`${i}-${j}`}
              x={i * 46 + 2}
              y={j * 42 + 2}
              width={40}
              height={36}
              rx={4}
              fill={`rgba(180,190,220,${0.08 + ((i * 7 + j * 3) % 7) * 0.01})`}
            />
          )),
        )}

        {/* AI prediction zones */}
        {aiZones.map((z, i) => (
          <rect
            key={i}
            x={z.x}
            y={z.y}
            width={z.width}
            height={z.height}
            rx={8}
            fill="rgba(94,92,230,0.12)"
            stroke="rgba(94,92,230,0.35)"
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        ))}

        {/* Roads */}
        {roads.map((r, i) => (
          <line
            key={i}
            x1={r.x1}
            y1={r.y1}
            x2={r.x2}
            y2={r.y2}
            stroke={r.color}
            strokeWidth={r.width}
            strokeLinecap="round"
            opacity={0.85}
          />
        ))}

        {/* Road labels */}
        {roads
          .filter((r) => r.label)
          .map((r, i) => (
            <text
              key={i}
              x={(r.x1 + r.x2) / 2}
              y={(r.y1 + r.y2) / 2 - 7}
              fill={r.color}
              fontSize="10"
              fontFamily="Inter, sans-serif"
              fontWeight="600"
              opacity={0.9}
              textAnchor="middle"
            >
              {r.label}
            </text>
          ))}

        {/* Measurement spots */}
        {spots.map((s, i) => (
          <g key={i}>
            {s.pulse && (
              <circle
                cx={s.cx}
                cy={s.cy}
                r={s.r + 5}
                fill={s.color}
                opacity={0.2}
              >
                <animate
                  attributeName="r"
                  values={`${s.r + 2};${s.r + 10};${s.r + 2}`}
                  dur="2s"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="opacity"
                  values="0.3;0;0.3"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
            )}
            <circle cx={s.cx} cy={s.cy} r={s.r} fill={s.color} opacity={0.9} />
            <circle
              cx={s.cx}
              cy={s.cy}
              r={s.r - 2}
              fill="white"
              opacity={0.5}
            />
          </g>
        ))}

        {/* Han River */}
        <path
          d="M0 200 Q200 195 400 205 Q600 215 800 200"
          stroke="rgba(100,160,240,0.45)"
          strokeWidth="22"
          fill="none"
          strokeLinecap="round"
        />
        <text
          x="350"
          y="208"
          fill="rgba(60,120,200,0.7)"
          fontSize="10"
          fontFamily="Inter"
          fontWeight="500"
        >
          한강
        </text>
      </svg>

      {/* Gradient overlay at bottom for card readability */}
      <div
        className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none"
        style={{
          background:
            "linear-gradient(to top, rgba(238,240,245,0.6), transparent)",
        }}
      />

      {/* Map type badge */}
      <div
        className="glass absolute top-3 right-3 px-3 py-1.5"
        style={{ borderRadius: 12 }}
      >
        <span
          className="text-xs font-semibold"
          style={{ color: "#007aff", fontFamily: "var(--font-body)" }}
        >
          지도 UI 데모
        </span>
      </div>

      {/* Legend */}
      <div
        className="glass absolute bottom-3 left-3 flex items-center gap-3 px-3 py-2"
        style={{ borderRadius: 12 }}
      >
        {[
          { color: "#34c759", label: "원활" },
          { color: "#ff9500", label: "서행" },
          { color: "#ff3b30", label: "혼잡" },
          { color: "#5e5ce6", label: "AI 예측" },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div
              className="w-3 h-1.5 rounded-full"
              style={{ background: item.color }}
            />
            <span
              style={{
                fontSize: 11,
                color: "#4a4a68",
                fontFamily: "var(--font-body)",
              }}
            >
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

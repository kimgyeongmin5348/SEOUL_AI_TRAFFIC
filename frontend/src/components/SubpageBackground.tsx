export default function SubpageBackground() {
  return (
    <div
      aria-hidden="true"
      className="app-backdrop fixed inset-0 pointer-events-none overflow-hidden select-none"
      style={{ zIndex: 0 }}
    >
      {/* Seoul Downtown Night Skyline & Traffic Background */}
      <div
        className="absolute inset-0 bg-cover bg-no-repeat"
        style={{
          backgroundImage: "url('/seoul-bg.jpg')",
          backgroundPosition: "center 28%",
          opacity: 0.38,
          filter: "brightness(0.88) contrast(1.08) saturate(1.15)",
        }}
      />

      {/* Seamless blending overlays matching base color #0c1424 */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            linear-gradient(180deg, rgba(12, 20, 36, 0.7) 0%, rgba(12, 20, 36, 0.32) 35%, rgba(12, 20, 36, 0.78) 75%, #0c1424 100%),
            radial-gradient(ellipse at 85% 10%, rgba(27, 49, 80, 0.45) 0%, transparent 60%)
          `,
        }}
      />

      {/* Edge gradient softening to ensure zero color boundary */}
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(to bottom, #0c1424 0%, transparent 6%, transparent 92%, #0c1424 100%)",
          opacity: 0.85,
        }}
      />

      {/* Grid overlay for tech / dashboard texture */}
      <div className="app-backdrop-grid" style={{ opacity: 0.3 }} />
    </div>
  )
}

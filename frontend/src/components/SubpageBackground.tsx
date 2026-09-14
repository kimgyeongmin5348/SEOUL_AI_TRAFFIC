export default function SubpageBackground() {
  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none overflow-hidden select-none"
      style={{ zIndex: 0 }}
    >
      {/* Full-bleed Seoul night photo — clearly visible, blurred so it stays ambient & non-distracting */}
      <div
        className="absolute inset-0 bg-ambient-motion"
        style={{
          backgroundImage: `url("https://images.unsplash.com/photo-1555425293-16e3d1e49b85?w=1920&h=1080&fit=crop&auto=format")`,
          backgroundSize: "cover",
          backgroundPosition: "center top",
          filter: "blur(12px)",
        }}
      />

      {/* Dark overlay for readability and consistency with main landing */}
      <div
        className="absolute inset-0"
        style={{
          background: "rgba(10, 14, 28, 0.62)",
        }}
      />
    </div>
  )
}

type BrandLogoProps = {
  className?: string
  priority?: boolean
}

export default function BrandLogo({ className = "", priority = false }: BrandLogoProps) {
  return (
    <span className={`brand-logo-shine block ${className}`}>
      <img
        src="/brand/rp-logo.png"
        alt="RoadPulse"
        className="block h-full w-full object-contain"
        width="768"
        height="512"
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
        decoding="async"
      />
    </span>
  )
}

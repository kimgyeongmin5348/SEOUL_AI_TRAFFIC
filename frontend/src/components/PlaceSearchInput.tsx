import { useEffect, useRef, useState } from "react"
import { searchPlaces } from "../services/placeSearch"
import type { PlaceSuggestion } from "../types/place"

interface Props {
  label: string
  value: string
  placeholder: string
  selectedPlace: PlaceSuggestion | null
  onValueChange: (value: string) => void
  onSelect: (place: PlaceSuggestion) => void
  onSubmit?: () => void
}

export default function PlaceSearchInput({
  label,
  value,
  placeholder,
  selectedPlace,
  onValueChange,
  onSelect,
  onSubmit,
}: Props) {
  const [results, setResults] = useState<PlaceSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const requestId = useRef(0)

  useEffect(() => {
    const query = value.trim()

    if (selectedPlace || query.length < 2) {
      setResults([])
      setOpen(false)
      return
    }

    const timer = window.setTimeout(async () => {
      const id = ++requestId.current
      setLoading(true)

      try {
        const items = await searchPlaces(query)

        if (id !== requestId.current) return

        setResults(items)
        setOpen(true)
      } catch {
        if (id !== requestId.current) return
        setResults([])
        setOpen(false)
      } finally {
        if (id === requestId.current) {
          setLoading(false)
        }
      }
    }, 300)

    return () => window.clearTimeout(timer)
  }, [value, selectedPlace])

  return (
    <div className="relative flex-1 w-full">
      <label className="sr-only">{label}</label>

      <input
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full rounded-xl bg-white px-4 py-3 text-sm outline-none"
        onFocus={() => {
          if (results.length > 0) setOpen(true)
        }}
        onChange={(event) => {
          onValueChange(event.target.value)
          setOpen(true)
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false)
          if (event.key === "Enter" && selectedPlace) onSubmit?.()
        }}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 100)
        }}
      />

      {loading && (
        <span className="absolute right-3 top-3 text-xs text-gray-400">
          검색 중…
        </span>
      )}

      {open && results.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-xl border bg-white shadow-xl">
          {results.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                className="w-full px-4 py-3 text-left hover:bg-gray-50"
                onMouseDown={(event) => {
                  // input의 blur보다 선택 처리가 먼저 실행되게 함
                  event.preventDefault()
                  onSelect(place)
                  setOpen(false)
                }}
              >
                <div className="text-sm font-semibold text-[#1a1a2e]">
                  {place.name}
                </div>

                <div className="mt-1 text-xs text-[#6b6b8a]">
                  {place.roadAddress || place.address}
                </div>

                {place.category && place.category !== "주소" && (
                  <div className="mt-1 text-[11px] text-gray-400">
                    {place.category}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

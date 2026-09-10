export interface PlaceSuggestion {
  id: string
  name: string
  address: string
  roadAddress: string
  category: string
  lat: number
  lng: number
  source: "keyword" | "address" | "current"
}
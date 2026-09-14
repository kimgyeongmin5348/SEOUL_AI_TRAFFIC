import { loadKakaoMaps } from "./kakaoMaps"
import type { PlaceSuggestion } from "../types/place"

function searchByKeyword(
  sdk: typeof kakao,
  query: string,
): Promise<PlaceSuggestion[]> {
  return new Promise((resolve) => {
    const places = new sdk.maps.services.Places()

    places.keywordSearch(
      query,
      (results, status) => {
        if (status !== sdk.maps.services.Status.OK) {
          resolve([])
          return
        }

        const items = results
          .filter((item) => {
            const address = item.road_address_name || item.address_name
            return address.startsWith("서울")
          })
          .slice(0, 8)
          .map((item) => ({
            id: item.id,
            name: item.place_name,
            address: item.address_name,
            roadAddress: item.road_address_name,
            category: item.category_name,
            lat: Number(item.y),
            lng: Number(item.x),
            source: "keyword" as const,
          }))

        resolve(items)
      },
      {
        size: 10,
      },
    )
  })
}

function searchByAddress(
  sdk: typeof kakao,
  query: string,
): Promise<PlaceSuggestion[]> {
  return new Promise((resolve) => {
    const geocoder = new sdk.maps.services.Geocoder()

    geocoder.addressSearch(query, (results, status) => {
      if (status !== sdk.maps.services.Status.OK) {
        resolve([])
        return
      }

      const items = results
        .filter((item) => item.address_name.startsWith("서울"))
        .slice(0, 5)
        .map((item, index) => ({
          id: `address-${item.x}-${item.y}-${index}`,
          name:
            item.road_address?.building_name ||
            item.road_address?.address_name ||
            item.address_name,
          address: item.address_name,
          roadAddress: item.road_address?.address_name || "",
          category: "주소",
          lat: Number(item.y),
          lng: Number(item.x),
          source: "address" as const,
        }))

      resolve(items)
    })
  })
}

export async function searchPlaces(
  rawQuery: string,
): Promise<PlaceSuggestion[]> {
  const query = rawQuery.trim()

  if (query.length < 2) {
    return []
  }

  const sdk = await loadKakaoMaps()

  const [keywordResults, addressResults] = await Promise.all([
    searchByKeyword(sdk, query),
    searchByAddress(sdk, query),
  ])

  const merged = [...keywordResults, ...addressResults]

  // 같은 위치가 양쪽 검색 결과에 들어오는 경우 제거
  return merged.filter((item, index, items) => {
    return (
      items.findIndex(
        (candidate) =>
          Math.abs(candidate.lat - item.lat) < 0.00001 &&
          Math.abs(candidate.lng - item.lng) < 0.00001,
      ) === index
    )
  }).slice(0, 8)
}

export async function resolvePlace(query: string): Promise<PlaceSuggestion> {
  const results = await searchPlaces(query)
  if (!results.length) {
    throw new Error(`"${query}" 위치를 찾지 못했습니다. 검색어를 더 구체적으로 입력해 주세요.`)
  }
  return results[0]
}

export async function reverseGeocodeCurrentLocation(
  lat: number,
  lng: number,
): Promise<PlaceSuggestion> {
  const sdk = await loadKakaoMaps()
  const geocoder = new sdk.maps.services.Geocoder()

  return new Promise((resolve, reject) => {
    geocoder.coord2Address(lng, lat, (results, status) => {
      if (status !== sdk.maps.services.Status.OK || !results.length) {
        reject(new Error("현재 위치의 주소를 확인하지 못했습니다."))
        return
      }

      const result = results[0]
      const address = result.address
      const road = result.road_address
      if (address?.region_1depth_name !== "서울" && address?.region_1depth_name !== "서울특별시") {
        reject(new Error("OUTSIDE_SEOUL"))
        return
      }

      const roadAddress = road?.address_name || ""
      const lotAddress = address?.address_name || ""
      resolve({
        id: `current-${lat.toFixed(6)}-${lng.toFixed(6)}`,
        name: roadAddress || lotAddress || "현 위치",
        address: lotAddress,
        roadAddress,
        category: "현재 위치",
        lat,
        lng,
        source: "current",
      })
    })
  })
}

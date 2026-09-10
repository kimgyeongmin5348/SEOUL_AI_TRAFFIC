type KakaoWindow = Window & { kakao?: typeof kakao }

let kakaoMapsPromise: Promise<typeof kakao> | null = null

function getKakao() {
  return (window as KakaoWindow).kakao
}

export function loadKakaoMaps(): Promise<typeof kakao> {
  const loadedKakao = getKakao()
  if (loadedKakao?.maps) {
    return new Promise((resolve) => {
      loadedKakao.maps.load(() => resolve(loadedKakao))
    })
  }

  if (kakaoMapsPromise) {
    return kakaoMapsPromise
  }

  kakaoMapsPromise = new Promise((resolve, reject) => {
    const appKey = import.meta.env.VITE_KAKAO_MAP_JS_KEY

    if (!appKey) {
      reject(new Error("VITE_KAKAO_MAP_JS_KEY가 설정되지 않았습니다."))
      return
    }

    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-kakao-map-sdk="true"]',
    )

    if (existing) {
      const existingKakao = getKakao()
      if (existingKakao?.maps) {
        existingKakao.maps.load(() => resolve(existingKakao))
        return
      }
      existing.addEventListener("load", () => {
        const sdk = getKakao()
        if (!sdk) {
          reject(new Error("카카오 지도 SDK가 초기화되지 않았습니다."))
          return
        }
        sdk.maps.load(() => resolve(sdk))
      }, { once: true })
      existing.addEventListener("error", () => {
        reject(new Error("카카오 지도 SDK를 불러오지 못했습니다."))
      }, { once: true })
      return
    }

    const script = document.createElement("script")

    script.dataset.kakaoMapSdk = "true"
    script.async = true
    script.src =
      `https://dapi.kakao.com/v2/maps/sdk.js` +
      `?appkey=${appKey}` +
      `&autoload=false` +
      `&libraries=services`

    script.onload = () => {
      const sdk = getKakao()
      if (!sdk) {
        kakaoMapsPromise = null
        reject(new Error("카카오 지도 SDK가 초기화되지 않았습니다."))
        return
      }
      sdk.maps.load(() => resolve(sdk))
    }

    script.onerror = () => {
      kakaoMapsPromise = null
      reject(new Error("카카오 지도 SDK를 불러오지 못했습니다."))
    }

    document.head.appendChild(script)
  })

  return kakaoMapsPromise
}

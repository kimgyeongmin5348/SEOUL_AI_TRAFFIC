import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

export interface User { id: number; email: string }

interface AuthValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

async function authRequest(path: string, body?: object) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(typeof data?.detail === "string" ? data.detail : "요청을 처리하지 못했습니다.")
  }
  return response.status === 204 ? null : response.json()
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authRequest("/api/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  const authenticate = async (path: string, email: string, password: string) => {
    const nextUser = await authRequest(path, { email, password })
    setUser(nextUser)
  }

  return (
    <AuthContext.Provider value={{
      user, loading,
      login: (email, password) => authenticate("/api/auth/login", email, password),
      signup: (email, password) => authenticate("/api/auth/signup", email, password),
      logout: async () => { await authRequest("/api/auth/logout", {}); setUser(null) },
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="min-h-full grid place-items-center bg-[#eef0f5] text-[#6b6b8a]">로그인 확인 중…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

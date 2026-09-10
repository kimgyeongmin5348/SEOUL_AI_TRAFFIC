import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AuthProvider, RequireAuth } from "./auth"

const Landing = lazy(() => import("./pages/Landing"))
const Dashboard = lazy(() => import("./pages/Dashboard"))
const RoutePage = lazy(() => import("./pages/Route"))
const Traffic = lazy(() => import("./pages/Traffic"))
const Incidents = lazy(() => import("./pages/Incidents"))
const Weather = lazy(() => import("./pages/Weather"))
const Prediction = lazy(() => import("./pages/Prediction"))
const Favorites = lazy(() => import("./pages/Favorites"))
const Login = lazy(() => import("./pages/Login"))

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Suspense
        fallback={
          <div className="min-h-full grid place-items-center bg-[#eef0f5] text-[#6b6b8a]">
            RoadPulse 불러오는 중…
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/route" element={<RoutePage />} />
          <Route path="/traffic" element={<Traffic />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/weather" element={<Weather />} />
          <Route path="/prediction" element={<Prediction />} />
          <Route path="/favorites" element={<RequireAuth><Favorites /></RequireAuth>} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}

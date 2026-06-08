import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useEffect, useState, lazy, Suspense } from 'react'
import { useAppStore } from '@/services/store'
import { api } from '@/services/api'
import ScalesIcon from '@/components/ui/ScalesIcon'
import { Spinner } from '@/components/ui/index'
import AppLayout from '@/components/layout/AppLayout'
import LanguagePicker from '@/pages/LanguagePicker'

// Lazy-loaded — keeps the initial bundle small so the landing page (above)
// paints immediately; each page's code downloads only when the user visits it.
const HomePage             = lazy(() => import('@/pages/HomePage'))
const ApplyPage            = lazy(() => import('@/pages/ApplyPage'))
const EmergencyPage        = lazy(() => import('@/pages/EmergencyPage'))
const AboutPage            = lazy(() => import('@/pages/AboutPage'))
const AdminPage            = lazy(() => import('@/pages/AdminPage'))
const NGOPage              = lazy(() => import('@/pages/NGOPage'))
const LawyersPage          = lazy(() => import('@/pages/LawyersPage'))
const DocumentAnalysisPage = lazy(() => import('@/pages/DocumentAnalysisPage'))

function PageFallback() {
  return (
    <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
      <Spinner size={32} />
    </div>
  )
}

function AppShell() {
  return <AppLayout><Outlet /></AppLayout>
}

export default function App() {
  const { setAppConfig, theme } = useAppStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    api.get('/api/config')
      .then(r => setAppConfig(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: '#0d1f3d' }}>
      <div className="text-center">
        <div
          className="w-20 h-20 rounded-[20px] flex items-center justify-center mx-auto mb-4"
          style={{
            background: 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
            boxShadow: '0 0 0 1px rgba(124,58,237,0.52), 0 0 24px rgba(124,58,237,0.58), 0 0 52px rgba(59,130,246,0.26)',
          }}
        >
          <ScalesIcon size={50} gid="apx" />
        </div>
        <p className="text-sm" style={{ color: 'rgba(255,255,255,0.4)' }}>Loading Pakistan AI Legal Aid…</p>
      </div>
    </div>
  )

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* Landing page — always shown at root */}
        <Route path="/" element={<LanguagePicker />} />

        {/* App — inside sidebar layout */}
        <Route element={<AppShell />}>
          <Route path="/home"      element={<HomePage />} />
          <Route path="/chat"      element={<Navigate to="/home" replace />} />
          <Route path="/apply"     element={<ApplyPage />} />
          <Route path="/emergency" element={<EmergencyPage />} />
          <Route path="/about"     element={<AboutPage />} />
          <Route path="/admin/*"   element={<AdminPage />} />
          <Route path="/analytics" element={<Navigate to="/admin/analytics" replace />} />
          <Route path="/ngos"                element={<NGOPage />} />
          <Route path="/lawyers"             element={<LawyersPage />} />
          <Route path="/document-analysis"   element={<DocumentAnalysisPage />} />
        </Route>

        {/* Unknown routes → back to landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

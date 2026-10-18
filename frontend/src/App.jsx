import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useEffect, lazy, Suspense } from 'react'
import { useAppStore } from '@/services/store'
import { api } from '@/services/api'
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
  const { setAppConfig, theme, language } = useAppStore()

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.lang = language === 'Urdu' ? 'ur' : 'en'
  }, [language])

  useEffect(() => {
    api.get('/api/config')
      .then(r => setAppConfig(r.data))
      .catch(() => {})
  }, [setAppConfig])

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* Landing page — always shown at root */}
        <Route path="/" element={<LanguagePicker />} />

        {/* Admin portal — separate URL, outside the user-facing sidebar layout */}
        <Route path="/admin-portal/*" element={<AdminPage />} />

        {/* App — inside sidebar layout */}
        <Route element={<AppShell />}>
          <Route path="/home"      element={<HomePage />} />
          <Route path="/chat"      element={<Navigate to="/home" replace />} />
          <Route path="/apply"     element={<ApplyPage />} />
          <Route path="/emergency" element={<EmergencyPage />} />
          <Route path="/about"     element={<AboutPage />} />
          <Route path="/analytics" element={<Navigate to="/admin-portal/analytics" replace />} />
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

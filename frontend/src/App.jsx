import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAppStore } from '@/services/store'
import { api } from '@/services/api'
import AppLayout from '@/components/layout/AppLayout'
import LanguagePicker from '@/pages/LanguagePicker'
import HomePage from '@/pages/HomePage'
import ApplyPage from '@/pages/ApplyPage'
import EmergencyPage from '@/pages/EmergencyPage'
import AboutPage from '@/pages/AboutPage'
import AdminPage from '@/pages/AdminPage'
import NGOPage from '@/pages/NGOPage'
import LawyersPage from '@/pages/LawyersPage'
import DocumentAnalysisPage from '@/pages/DocumentAnalysisPage'

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
        <div className="text-5xl mb-4">⚖️</div>
        <p className="text-sm" style={{ color: 'rgba(255,255,255,0.4)' }}>Loading Pakistan AI Legal Aid…</p>
      </div>
    </div>
  )

  return (
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
  )
}

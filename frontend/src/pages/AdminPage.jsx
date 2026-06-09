import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Routes, Route, useNavigate, Link, useLocation } from 'react-router-dom'
import { Lock, LayoutDashboard, Building2, Users, BarChart3, Route as RouteIcon, Plus, Pencil, Trash2, X, Check, Search, ToggleLeft, ToggleRight, RefreshCw, Settings2, Eye } from 'lucide-react'
import { useAppStore } from '@/services/store'
import { adminLogin, getApplicationStats, getApplications, updateApplicationStatus, assignLawyer, assignNGO, getNGOs, getLawyers, createNGO, updateNGO, deleteNGO, deactivateNGO, reactivateNGO, createLawyer, updateLawyer, deleteLawyer, setLawyerAvailability, rerouteApplication } from '@/services/api'
import { KPICard, Card, SectionHeader, StatusBadge, RiskBadge, Badge, Spinner, Alert } from '@/components/ui/index'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'
import AnalyticsPage from '@/pages/AnalyticsPage'
import { PageContainer } from '@/components/layout/PageLayout'

// ── Admin Login Gate ──────────────────────────────────────────────────────────
function AdminLoginGate({ onLogin }) {
  const [pw, setPw] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async () => {
    if (!pw) return
    setLoading(true)
    setError('')
    try {
      const r = await adminLogin(pw)
      onLogin(r.token)
    } catch {
      setError('Incorrect password. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-page)' }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <Card padding="p-8" className="w-full max-w-sm text-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-5"
            style={{ background: 'linear-gradient(135deg, #7C3AED, #3B82F6)', boxShadow: '0 0 28px rgba(124,58,237,0.40)' }}
          >
            🛡️
          </div>
          <h2 className="font-display text-xl font-semibold mb-1">Admin Access</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Enter your admin password to continue.</p>
          {error && <Alert type="danger" className="mb-4 text-left">⚠️ {error}</Alert>}
          <input
            type="password"
            value={pw}
            onChange={e => setPw(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            placeholder="Admin password"
            className="input mb-3"
          />
          <button onClick={handleLogin} disabled={loading} className="btn-primary w-full py-2.5 justify-center">
            {loading ? <Spinner size={16} /> : <Lock size={16} />}
            Login
          </button>
        </Card>
      </motion.div>
    </div>
  )
}

// ── Admin Tabs ────────────────────────────────────────────────────────────────
const TABS = [
  { path: '',        icon: LayoutDashboard, label: 'Dashboard' },
  { path: 'ngos',   icon: Building2,       label: 'NGO Registry' },
  { path: 'lawyers',icon: Users,           label: 'Lawyers' },
  { path: 'routing',icon: RouteIcon,       label: 'Case Routing' },
  { path: 'analytics', icon: BarChart3,    label: 'Analytics' },
]

function AdminNav() {
  const location = useLocation()
  return (
    <div className="flex gap-1 border-b mb-6 overflow-x-auto" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
      {TABS.map(tab => {
        const href = `/admin${tab.path ? '/' + tab.path : ''}`
        const active = location.pathname === href
        return (
          <Link
            key={tab.path}
            to={href}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors"
            style={{
              borderColor: active ? '#7C3AED' : 'transparent',
              color: active ? '#a78bfa' : 'var(--text-muted)',
            }}
          >
            <tab.icon size={14} /> {tab.label}
          </Link>
        )
      })}
    </div>
  )
}

// ── Dashboard Tab ─────────────────────────────────────────────────────────────
function DashboardTab() {
  const [stats, setStats] = useState(null)
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [viewingApp, setViewingApp] = useState(null)

  useEffect(() => {
    Promise.all([getApplicationStats(), getApplications({ limit: 20 })])
      .then(([s, a]) => { setStats(s); setApps(a.applications || []) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><Spinner size={32} /></div>

  const statusData  = stats ? Object.entries(stats.by_status || {}).map(([k, v]) => ({ name: k, value: v })) : []
  const caseTypeData = Object.entries(stats?.by_case_type || {}).slice(0, 6).map(([k, v]) => ({ name: k.slice(0, 12), value: v }))

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard label="Total Applications" value={stats?.total || 0} icon="📋" />
        <KPICard label="Pending" value={stats?.by_status?.pending || 0} icon="⏳" />
        <KPICard label="Assigned" value={stats?.by_status?.assigned || 0} icon="📌" subColor="var(--success)" />
        <KPICard label="Resolved" value={stats?.by_status?.resolved || 0} icon="✅" subColor="var(--success-text)" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Status pie — semantic colors by name */}
        <Card padding="p-5">
          <div className="label mb-4">Applications by Status</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={statusData}
                dataKey="value"
                nameKey="name"
                cx="50%" cy="50%"
                outerRadius={70}
                innerRadius={24}
                paddingAngle={3}
              >
                {statusData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={STATUS_PIE_COLORS[entry.name] || '#8B5CF6'}
                    strokeWidth={0}
                  />
                ))}
              </Pie>
              <Legend {...CHART_LEGEND} />
              <Tooltip {...CHART_TOOLTIP} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* Case type bar — indigo→violet gradient */}
        <Card padding="p-5">
          <div className="label mb-4">Applications by Case Type</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={caseTypeData}>
              <defs>
                <linearGradient id="caseBarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#8B5CF6" stopOpacity={1}    />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity={0.75} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" tick={CHART_TICK} {...CHART_AXIS} />
              <YAxis               tick={CHART_TICK} {...CHART_AXIS} />
              <Tooltip {...CHART_TOOLTIP} />
              <Bar dataKey="value" fill="url(#caseBarGrad)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Applications table */}
      <Card padding="p-0">
        <div className="px-5 py-3 border-b flex items-center gap-2"
             style={{ borderColor: 'var(--border-muted)' }}>
          <span className="font-semibold text-sm">Recent Applications</span>
          <span className="badge badge-neutral">{apps.length}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table" style={{ tableLayout: 'fixed', width: '100%' }}>
            <colgroup>
              <col style={{ width: '14%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '15%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '15%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>ID</th><th>Name</th><th>Case Type</th><th>City</th>
                <th>Urgency</th><th>Status</th><th>View</th>
              </tr>
            </thead>
            <tbody>
              {apps.map(app => (
                <ApplicationRow
                  key={app.application_id}
                  app={app}
                  onView={() => setViewingApp(app)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <AnimatePresence>
        {viewingApp && (
          <AppDetailsModal app={viewingApp} onClose={() => setViewingApp(null)} />
        )}
      </AnimatePresence>
    </div>
  )
}

function ApplicationRow({ app, onView }) {
  return (
    <tr>
      <td className="font-mono text-[11px]" style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {app.application_id?.slice(-8)}
      </td>
      <td className="font-semibold text-sm" dir="auto" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {app.name}
      </td>
      <td className="text-xs" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {app.case_type}
      </td>
      <td className="text-xs" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {app.city}
      </td>
      <td><RiskBadge level={app.urgency?.toLowerCase()} /></td>
      <td><StatusBadge status={app.status} /></td>
      <td>
        <button
          onClick={onView}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            height: 26,
            padding: '0 10px',
            fontSize: 11,
            fontWeight: 500,
            borderRadius: 6,
            border: '1px solid var(--border-default)',
            background: 'transparent',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'background 0.14s, color 0.14s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'var(--text-primary)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)' }}
        >
          <Eye size={11} /> View
        </button>
      </td>
    </tr>
  )
}

// ── App Details Modal ─────────────────────────────────────────────────────────

function AppDetailsModal({ app, onClose }) {
  const { theme } = useAppStore()
  const isDark = theme === 'dark'
  const borderColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.09)'
  const sectionBg   = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)'

  const lawyerName    = app.suggested_lawyer ? app.suggested_lawyer.split('(')[0].trim() : ''
  const lawyerLicense = app.suggested_lawyer?.match(/\(([^)]+)\)/)?.[1] || ''

  const submittedFormatted = app.submitted_at
    ? new Date(app.submitted_at).toLocaleString('en-PK', { dateStyle: 'medium', timeStyle: 'short' })
    : null

  function FieldLabel({ children }) {
    return (
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 3 }}>
        {children}
      </div>
    )
  }

  function FieldValue({ children, mono, color }) {
    return (
      <div style={{ fontSize: 13, lineHeight: 1.4, color: color || 'var(--text-primary)', fontFamily: mono ? 'monospace' : undefined }}>
        {children}
      </div>
    )
  }

  function Divider() {
    return <div style={{ height: 1, background: borderColor }} />
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 8 }}
        transition={{ duration: 0.18 }}
        className="card w-full flex flex-col"
        style={{ maxWidth: 860, maxHeight: '90vh', padding: 0, boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0" style={{ borderColor }}>
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: 'linear-gradient(135deg,#7C3AED,#3B82F6)' }}
            >
              <Eye size={14} color="#fff" />
            </div>
            <div>
              <div className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Application Details</div>
              <div className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{app.application_id}</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <X size={16} />
          </button>
        </div>

        {/* Two-column body */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 min-h-full" style={{ borderColor }}>

            {/* ── Left: Applicant + Case Metadata ── */}
            <div className="px-6 py-6 space-y-6 border-b md:border-b-0 md:border-r" style={{ borderColor }}>

              {/* Applicant */}
              <div>
                <div className="label mb-3">Applicant</div>
                <div className="flex items-baseline gap-2 mb-2">
                  <span dir="auto" className="font-semibold text-base" style={{ color: 'var(--text-primary)' }}>{app.name || '—'}</span>
                  {app.city && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{app.city}</span>}
                </div>
                <div className="space-y-1.5">
                  {app.phone && (
                    <div className="flex items-center gap-2">
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', width: 44, flexShrink: 0 }}>Phone</span>
                      <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{app.phone}</span>
                    </div>
                  )}
                  {app.email && (
                    <div className="flex items-center gap-2">
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', width: 44, flexShrink: 0 }}>Email</span>
                      <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{app.email}</span>
                    </div>
                  )}
                  {app.cnic && (
                    <div className="flex items-center gap-2">
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', width: 44, flexShrink: 0 }}>CNIC</span>
                      <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{app.cnic}</span>
                    </div>
                  )}
                </div>
              </div>

              <Divider />

              {/* Case metadata */}
              <div>
                <div className="label mb-3">Case</div>
                <div className="flex items-center gap-2 flex-wrap mb-3">
                  {app.case_type && (
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium" style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-secondary)', border: '1px solid rgba(255,255,255,0.10)' }}>
                      {app.case_type}
                    </span>
                  )}
                  <RiskBadge level={app.urgency?.toLowerCase()} />
                  <StatusBadge status={app.status} />
                </div>
                {submittedFormatted && (
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', flexShrink: 0 }}>Submitted</span>
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{submittedFormatted}</span>
                  </div>
                )}
              </div>

              <Divider />

              {/* Assignments */}
              <div>
                <div className="label mb-3">Assignments</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FieldLabel>NGO</FieldLabel>
                    {app.assigned_ngo
                      ? <FieldValue color="#10B981">{app.assigned_ngo}</FieldValue>
                      : <FieldValue color="var(--text-muted)">Unassigned</FieldValue>
                    }
                  </div>
                  <div>
                    <FieldLabel>Lawyer</FieldLabel>
                    {lawyerName
                      ? <FieldValue color="#60A5FA">{lawyerName}{lawyerLicense && <span style={{ opacity: 0.65, fontSize: 11 }}> · {lawyerLicense}</span>}</FieldValue>
                      : <FieldValue color="var(--text-muted)">Unassigned</FieldValue>
                    }
                  </div>
                </div>
              </div>
            </div>

            {/* ── Right: Description + Routing Notes ── */}
            <div className="px-6 py-6 space-y-6">

              {/* Case description */}
              <div>
                <div className="label mb-3">Case Description</div>
                {app.description ? (
                  <p
                    dir="auto"
                    className="text-[13px] leading-relaxed"
                    style={{
                      color: 'var(--text-secondary)',
                      padding: '12px 14px',
                      borderRadius: 8,
                      background: sectionBg,
                      border: `1px solid ${borderColor}`,
                      margin: 0,
                    }}
                  >
                    {app.description}
                  </p>
                ) : (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No description provided.</p>
                )}
              </div>

              {/* Routing notes */}
              <div>
                <div className="label mb-3">Routing Notes</div>
                {app.notes ? (
                  <p
                    className="text-[12px] leading-relaxed"
                    style={{
                      color: 'var(--text-secondary)',
                      borderLeft: '2px solid rgba(100,116,139,0.35)',
                      paddingLeft: 10,
                      margin: 0,
                    }}
                  >
                    {app.notes}
                  </p>
                ) : (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No routing note recorded.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end shrink-0 px-6 py-3 border-t" style={{ borderColor }}>
          <button onClick={onClose} className="btn-secondary px-5 py-2 text-sm">Close</button>
        </div>
      </motion.div>
    </div>,
    document.body
  )
}

// ── NGO Registry Tab ──────────────────────────────────────────────────────────

const NGO_CITIES = ['Karachi','Lahore','Islamabad','Rawalpindi','Peshawar','Quetta','Multan','Faisalabad']
const NGO_ALL_CATEGORIES = [
  'Family Law','Criminal Law','Labour Law','Property Law','Inheritance Law',
  'Cybercrime','Harassment','Civil Law / Procedure','Contract Law',
  'Consumer Rights','Constitutional Law','General / Other',
]
const CAT_COLOR = {
  'Family Law':'#EC4899','Criminal Law':'#EF4444','Labour Law':'#F59E0B',
  'Property Law':'#8B5CF6','Inheritance Law':'#7C3AED','Cybercrime':'#06B6D4',
  'Harassment':'#F97316','Civil Law / Procedure':'#3B82F6','Contract Law':'#10B981',
  'Consumer Rights':'#84CC16','Constitutional Law':'#6366F1','General / Other':'#64748B',
}
const catColor = (c) => CAT_COLOR[c] || '#64748B'

const EMPTY_NGO_FORM = {
  name: '', city: '', contact: '', email: '',
  categories: [], handles_all_cases: false, active: true,
}

function NGOFormModal({ ngo, onSave, onClose, saving, error }) {
  const isEdit  = Boolean(ngo)
  const { theme } = useAppStore()
  const isDark  = theme === 'dark'

  const borderMuted = isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.12)'
  const tagBorder   = isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)'
  const tagBg       = isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)'
  const toggleOff   = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'

  const [form, setForm] = useState(() => isEdit ? {
    name:              ngo.ngo_name        || '',
    city:              ngo.city            || '',
    contact:           ngo.contact_phone   || '',
    email:             ngo.contact_email   || '',
    categories:        Array.isArray(ngo.categories) ? ngo.categories : [],
    handles_all_cases: Boolean(ngo.handles_all_cases),
    active:            ngo.active !== 0,
  } : { ...EMPTY_NGO_FORM })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const toggleCat = (cat) => setForm(f => ({
    ...f,
    categories: f.categories.includes(cat)
      ? f.categories.filter(c => c !== cat)
      : [...f.categories, cat],
  }))

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave(form)
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.18 }}
        className="card w-full max-w-xl max-h-[90vh] overflow-y-auto"
        style={{ padding: '1.5rem', boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold text-base" style={{ color: 'var(--text-primary)' }}>
            {isEdit ? 'Edit NGO' : 'Add NGO'}
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <X size={16} />
          </button>
        </div>

        {error && <Alert type="danger" className="mb-4">⚠️ {error}</Alert>}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="label mb-1 block">Organization Name *</label>
            <input
              className="input"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder="e.g. Legal Aid Society Karachi"
              required
            />
          </div>

          {/* City + Contact */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label mb-1 block">City</label>
              <select className="input" value={form.city} onChange={e => set('city', e.target.value)}>
                <option value="">— Select city —</option>
                {NGO_CITIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label mb-1 block">Contact / Phone</label>
              <input
                className="input"
                value={form.contact}
                onChange={e => set('contact', e.target.value)}
                placeholder="e.g. 021-35765145"
              />
            </div>
          </div>

          {/* Email */}
          <div>
            <label className="label mb-1 block">Email</label>
            <input
              className="input"
              type="email"
              value={form.email}
              onChange={e => set('email', e.target.value)}
              placeholder="contact@ngo.org"
            />
          </div>

          {/* Categories — multi-select tags */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="label">Areas of Law *</label>
              {form.categories.length > 0 && (
                <button
                  type="button"
                  onClick={() => setForm(f => ({ ...f, categories: [] }))}
                  className="text-[10px] transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                >
                  Clear all
                </button>
              )}
            </div>

            {/* Selected tags */}
            {form.categories.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {form.categories.map(cat => {
                  const color = catColor(cat)
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => toggleCat(cat)}
                      className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full transition-all select-none group"
                      style={{
                        background: `${color}28`,
                        color,
                        border: `1px solid ${color}55`,
                      }}
                      title={`Remove ${cat}`}
                    >
                      {cat}
                      <X size={9} strokeWidth={2.5} className="opacity-60 group-hover:opacity-100" />
                    </button>
                  )
                })}
              </div>
            )}

            {/* Available tags (unselected) */}
            <div
              className="flex flex-wrap gap-1.5 p-3 rounded-xl border"
              style={{ borderColor: borderMuted, background: tagBg }}
            >
              {NGO_ALL_CATEGORIES.filter(c => !form.categories.includes(c)).length === 0 ? (
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  All categories selected
                </span>
              ) : (
                NGO_ALL_CATEGORIES.filter(c => !form.categories.includes(c)).map(cat => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCat(cat)}
                    className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full transition-all select-none"
                    style={{
                      color: 'var(--text-muted)',
                      border: `1px dashed ${tagBorder}`,
                      background: 'transparent',
                    }}
                    onMouseEnter={e => {
                      const color = catColor(cat)
                      e.currentTarget.style.color = color
                      e.currentTarget.style.borderColor = color + '66'
                      e.currentTarget.style.background = color + '12'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.color = 'var(--text-muted)'
                      e.currentTarget.style.borderColor = tagBorder
                      e.currentTarget.style.background = 'transparent'
                    }}
                    title={`Add ${cat}`}
                  >
                    + {cat}
                  </button>
                ))
              )}
            </div>

            {form.categories.length === 0 && (
              <p className="text-[10px] mt-1.5" style={{ color: 'var(--text-muted)' }}>
                Click a category above to add it
              </p>
            )}
          </div>

          {/* Handles All Cases + Active */}
          <div className="flex items-center gap-6 pt-1">
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <span
                className="w-9 h-5 rounded-full relative transition-colors flex-shrink-0"
                style={{ background: form.handles_all_cases ? '#7C3AED' : toggleOff }}
                onClick={() => set('handles_all_cases', !form.handles_all_cases)}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                  style={{ transform: form.handles_all_cases ? 'translateX(16px)' : 'translateX(0)' }}
                />
              </span>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Handles All Case Types</span>
            </label>

            {isEdit && (
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <span
                  className="w-9 h-5 rounded-full relative transition-colors flex-shrink-0"
                  style={{ background: form.active ? '#10B981' : toggleOff }}
                  onClick={() => set('active', !form.active)}
                >
                  <span
                    className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                    style={{ transform: form.active ? 'translateX(16px)' : 'translateX(0)' }}
                  />
                </span>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Active</span>
              </label>
            )}
          </div>

          {/* Buttons */}
          <div className="flex justify-end gap-2 pt-2 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
            <button type="button" onClick={onClose} className="btn-secondary px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="btn-primary px-4 py-2 text-sm justify-center">
              {saving ? <Spinner size={14} /> : <Check size={14} />}
              {isEdit ? 'Save Changes' : 'Add NGO'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>,
    document.body
  )
}

function NGOTab() {
  const [ngos,        setNgos]        = useState([])
  const [loading,     setLoading]     = useState(true)
  const [modal,       setModal]       = useState({ open: false, ngo: null })
  const [deleteTarget,setDeleteTarget]= useState(null)
  const [saving,      setSaving]      = useState(false)
  const [formError,   setFormError]   = useState('')
  const [search,      setSearch]      = useState('')

  const refresh = useCallback(() => {
    setLoading(true)
    getNGOs().then(r => setNgos(r.ngos || [])).finally(() => setLoading(false))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const openCreate = () => { setModal({ open: true, ngo: null }); setFormError('') }
  const openEdit   = (ngo) => { setModal({ open: true, ngo });   setFormError('') }
  const closeModal = () => setModal({ open: false, ngo: null })

  const handleSave = async (formData) => {
    setSaving(true)
    setFormError('')
    try {
      if (modal.ngo) {
        await updateNGO(modal.ngo.ngo_id, formData)
      } else {
        await createNGO(formData)
      }
      closeModal()
      refresh()
    } catch (e) {
      setFormError(e.response?.data?.detail || 'Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try { await deleteNGO(deleteTarget.ngo_id) } catch {}
    setDeleteTarget(null)
    refresh()
  }

  const handleToggleActive = async (ngo) => {
    try {
      ngo.active ? await deactivateNGO(ngo.ngo_id) : await reactivateNGO(ngo.ngo_id)
      refresh()
    } catch {}
  }

  const filtered = ngos.filter(n =>
    !search ||
    n.ngo_name?.toLowerCase().includes(search.toLowerCase()) ||
    n.city?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      <Card padding="p-0">
        {/* Header */}
        <div className="px-5 py-3 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: 'var(--border-muted)' }}>
          <span className="font-semibold text-sm">NGO Registry</span>
          <span className="badge badge-neutral">{ngos.length}</span>
          <div className="relative ml-auto">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search name or city…"
              className="input pl-7 text-xs h-8"
              style={{ width: 200 }}
            />
          </div>
          <button onClick={openCreate} className="btn-primary px-3 py-1.5 text-xs gap-1.5">
            <Plus size={13} /> Add NGO
          </button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-10"><Spinner size={28} /></div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-10 text-sm" style={{ color: 'var(--text-muted)' }}>
            {search ? 'No NGOs match your search.' : 'No NGOs registered yet. Click "Add NGO" to start.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Categories</th>
                  <th>City</th>
                  <th>Contact</th>
                  <th>Email</th>
                  <th>Handles All</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(ngo => (
                  <NGORow
                    key={ngo.ngo_id}
                    ngo={ngo}
                    onEdit={() => openEdit(ngo)}
                    onDelete={() => setDeleteTarget(ngo)}
                    onToggleActive={() => handleToggleActive(ngo)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create / Edit modal */}
      {modal.open && (
        <NGOFormModal
          ngo={modal.ngo}
          onSave={handleSave}
          onClose={closeModal}
          saving={saving}
          error={formError}
        />
      )}

      {/* Delete confirmation */}
      {deleteTarget && createPortal(
        <div
          className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={e => { if (e.target === e.currentTarget) setDeleteTarget(null) }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="card p-6 max-w-sm w-full"
            style={{ boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
          >
            <div className="text-center mb-4">
              <div className="text-3xl mb-2">🗑️</div>
              <h4 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>Delete NGO</h4>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Permanently delete <strong style={{ color: 'var(--text-primary)' }}>{deleteTarget.ngo_name}</strong>? This cannot be undone.
              </p>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary flex-1 py-2 text-sm justify-center" onClick={() => setDeleteTarget(null)}>
                Cancel
              </button>
              <button
                className="flex-1 py-2 text-sm rounded-xl font-medium flex items-center justify-center gap-1.5 transition-colors"
                style={{ background: '#ef4444', color: '#fff' }}
                onMouseEnter={e => e.currentTarget.style.background = '#dc2626'}
                onMouseLeave={e => e.currentTarget.style.background = '#ef4444'}
                onClick={handleDelete}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          </motion.div>
        </div>,
        document.body
      )}
    </>
  )
}

function NGORow({ ngo, onEdit, onDelete, onToggleActive }) {
  const cats = Array.isArray(ngo.categories) ? ngo.categories : []

  return (
    <tr>
      <td>
        <div className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{ngo.ngo_name}</div>
        <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>{ngo.ngo_id}</div>
      </td>
      <td>
        <div className="flex flex-wrap gap-1">
          {cats.slice(0, 2).map(cat => (
            <span
              key={cat}
              className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold whitespace-nowrap"
              style={{
                background: `${catColor(cat)}22`,
                color: catColor(cat),
                border: `1px solid ${catColor(cat)}44`,
              }}
            >
              {cat}
            </span>
          ))}
          {cats.length > 2 && (
            <span
              className="text-[9px] px-1.5 py-0.5 rounded-full"
              style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}
              title={cats.slice(2).join(', ')}
            >
              +{cats.length - 2}
            </span>
          )}
        </div>
      </td>
      <td className="text-xs">{ngo.city || '—'}</td>
      <td className="text-xs font-mono">{ngo.contact_phone || '—'}</td>
      <td className="text-xs">{ngo.contact_email || '—'}</td>
      <td>
        {ngo.handles_all_cases
          ? <Badge variant="primary">Yes</Badge>
          : <span className="text-xs" style={{ color: 'var(--text-muted)' }}>No</span>
        }
      </td>
      <td>
        <button
          onClick={onToggleActive}
          title={ngo.active ? 'Click to deactivate' : 'Click to activate'}
          className="flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5 transition-opacity hover:opacity-75"
          style={{
            background: ngo.active ? 'rgba(16,185,129,0.15)' : 'rgba(100,116,139,0.15)',
            color:      ngo.active ? '#10B981' : '#64748B',
            border:     `1px solid ${ngo.active ? '#10B98133' : '#64748B33'}`,
          }}
        >
          {ngo.active ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
          {ngo.active ? 'Active' : 'Inactive'}
        </button>
      </td>
      <td>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Edit"
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: '#f87171' }}
            title="Delete"
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.12)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── Lawyers Tab ───────────────────────────────────────────────────────────────

const LAWYER_CATEGORIES = [
  'Family Law','Criminal Law','Labour Law','Property Law','Inheritance Law',
  'Cybercrime','Harassment','Civil Law / Procedure','Contract Law',
  'Consumer Rights','Constitutional Law','General / Other',
]

const BAR_LICENSE_HINT = {
  Lahore:     'e.g. LHC-1056',
  Karachi:    'e.g. KHC-1056',
  Islamabad:  'e.g. IHC-1056',
  Rawalpindi: 'e.g. LHC-1056',
  Peshawar:   'e.g. PHC-1056',
  Quetta:     'e.g. BHC-1056',
  Multan:     'e.g. MHC-1056',
  Faisalabad: 'e.g. LHC-1056',
}

const EMPTY_LAWYER_FORM = {
  full_name: '', bar_license: '', city: '',
  expertise_main: '', ngo_id: '', available: true,
}

function LawyerFormModal({ lawyer, onSave, onClose, saving, error }) {
  const isEdit = Boolean(lawyer)
  const { theme } = useAppStore()
  const isDark   = theme === 'dark'
  const borderMuted = isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.12)'
  const toggleOff   = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'

  const [form, setForm] = useState(() => isEdit ? {
    full_name:      lawyer.full_name      || '',
    bar_license:    lawyer.bar_license    || '',
    city:           lawyer.city          || '',
    expertise_main: lawyer.expertise_main || '',
    ngo_id:         lawyer.ngo_id        || '',
    available:      lawyer.available !== false,
  } : { ...EMPTY_LAWYER_FORM })

  const [ngos, setNgos] = useState([])
  useEffect(() => {
    getNGOs().then(r => setNgos(r.ngos || [])).catch(() => {})
  }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  // Derive which categories are available based on the selected NGO.
  // If no NGO selected, or NGO handles all cases → show all categories.
  const selectedNgo = ngos.find(n => n.ngo_id === form.ngo_id)
  const ngoFiltered = Boolean(selectedNgo && !selectedNgo.handles_all_cases)
  const availableCategories = ngoFiltered
    ? LAWYER_CATEGORIES.filter(c =>
        Array.isArray(selectedNgo.categories) && selectedNgo.categories.includes(c)
      )
    : LAWYER_CATEGORIES

  // When NGO changes, also clear expertise_main if it's no longer available.
  const handleNgoChange = (ngoId) => {
    const ngo = ngos.find(n => n.ngo_id === ngoId)
    const allowed = !ngoId || !ngo || ngo.handles_all_cases
      ? LAWYER_CATEGORIES
      : (Array.isArray(ngo.categories) ? ngo.categories : [])
    setForm(f => ({
      ...f,
      ngo_id: ngoId,
      expertise_main: allowed.includes(f.expertise_main) ? f.expertise_main : '',
    }))
  }

  const handleSubmit = (e) => { e.preventDefault(); onSave(form) }

  const licPlaceholder = BAR_LICENSE_HINT[form.city] || 'e.g. LHC-1056'

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.18 }}
        className="card w-full max-w-lg max-h-[90vh] overflow-y-auto"
        style={{ padding: '1.5rem', boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold text-base" style={{ color: 'var(--text-primary)' }}>
            {isEdit ? 'Edit Lawyer' : 'Add Lawyer'}
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <X size={16} />
          </button>
        </div>

        {error && <Alert type="danger" className="mb-4">⚠️ {error}</Alert>}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Full Name */}
          <div>
            <label className="label mb-1 block">Full Name *</label>
            <input
              className="input"
              value={form.full_name}
              onChange={e => set('full_name', e.target.value)}
              placeholder="e.g. Adv. Ahmed Hassan"
              required
            />
          </div>

          {/* City + Bar License */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label mb-1 block">City *</label>
              <select className="input" value={form.city} onChange={e => set('city', e.target.value)} required>
                <option value="">— Select city —</option>
                {NGO_CITIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label mb-1 block">Bar License No. *</label>
              <input
                className="input font-mono"
                value={form.bar_license}
                onChange={e => set('bar_license', e.target.value.toUpperCase())}
                placeholder={licPlaceholder}
                required
              />
            </div>
          </div>

          {/* Assign to NGO — shown first so category list can be filtered */}
          <div>
            <label className="label mb-1 block">
              Assign to NGO
              <span className="ml-1 font-normal text-[10px]" style={{ color: 'var(--text-muted)' }}>(optional)</span>
            </label>
            <select className="input" value={form.ngo_id} onChange={e => handleNgoChange(e.target.value)}>
              <option value="">— No NGO —</option>
              {ngos.filter(n => n.active !== 0).map(n => (
                <option key={n.ngo_id} value={n.ngo_id}>{n.ngo_name}{n.city ? ` · ${n.city}` : ''}</option>
              ))}
            </select>
          </div>

          {/* Category — filtered to NGO's case types when an NGO is selected */}
          <div>
            <label className="label mb-1 block">Category / Expertise *</label>
            <select className="input" value={form.expertise_main} onChange={e => set('expertise_main', e.target.value)} required>
              <option value="">— Select category —</option>
              {availableCategories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {ngoFiltered && (
              <p className="mt-1 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Showing {availableCategories.length} of {LAWYER_CATEGORIES.length} categories handled by {selectedNgo.ngo_name}
              </p>
            )}
          </div>

          {/* Available toggle (edit only) */}
          {isEdit && (
            <div
              className="flex items-center justify-between px-3 py-2.5 rounded-xl border"
              style={{ borderColor: borderMuted }}
            >
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Available for new cases</span>
              <span
                className="w-9 h-5 rounded-full relative transition-colors flex-shrink-0 cursor-pointer"
                style={{ background: form.available ? '#10B981' : toggleOff }}
                onClick={() => set('available', !form.available)}
              >
                <span
                  className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                  style={{ transform: form.available ? 'translateX(16px)' : 'translateX(0)' }}
                />
              </span>
            </div>
          )}

          {/* Buttons */}
          <div className="flex justify-end gap-2 pt-2 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
            <button type="button" onClick={onClose} className="btn-secondary px-4 py-2 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="btn-primary px-4 py-2 text-sm justify-center">
              {saving ? <Spinner size={14} /> : <Check size={14} />}
              {isEdit ? 'Save Changes' : 'Add Lawyer'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>,
    document.body
  )
}

function LawyersTab() {
  const [lawyers,     setLawyers]     = useState([])
  const [ngoMap,      setNgoMap]      = useState({})
  const [loading,     setLoading]     = useState(true)
  const [modal,       setModal]       = useState({ open: false, lawyer: null })
  const [deleteTarget,setDeleteTarget]= useState(null)
  const [saving,      setSaving]      = useState(false)
  const [formError,   setFormError]   = useState('')
  const [search,      setSearch]      = useState('')

  const refresh = useCallback(() => {
    setLoading(true)
    Promise.all([
      getLawyers().then(r => r.lawyers || []),
      getNGOs().then(r => r.ngos || []),
    ]).then(([ls, ns]) => {
      setLawyers(ls)
      setNgoMap(Object.fromEntries(ns.map(n => [n.ngo_id, n.ngo_name])))
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const openCreate  = () => { setModal({ open: true, lawyer: null }); setFormError('') }
  const openEdit    = (l) => { setModal({ open: true, lawyer: l });   setFormError('') }
  const closeModal  = () => setModal({ open: false, lawyer: null })

  const handleSave = async (formData) => {
    setSaving(true)
    setFormError('')
    try {
      if (modal.lawyer) {
        await updateLawyer(modal.lawyer.lawyer_id, formData)
      } else {
        await createLawyer(formData)
      }
      closeModal()
      refresh()
    } catch (e) {
      setFormError(e.response?.data?.detail || 'Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try { await deleteLawyer(deleteTarget.lawyer_id) } catch {}
    setDeleteTarget(null)
    refresh()
  }

  const handleToggleAvailable = async (l) => {
    try { await setLawyerAvailability(l.lawyer_id, !l.available); refresh() } catch {}
  }

  const filtered = lawyers.filter(l =>
    !search ||
    l.full_name?.toLowerCase().includes(search.toLowerCase()) ||
    l.bar_license?.toLowerCase().includes(search.toLowerCase()) ||
    l.city?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      <Card padding="p-0">
        {/* Header */}
        <div className="px-5 py-3 border-b flex items-center gap-3 flex-wrap" style={{ borderColor: 'var(--border-muted)' }}>
          <span className="font-semibold text-sm">Lawyer Registry</span>
          <span className="badge badge-neutral">{lawyers.length}</span>
          <div className="relative ml-auto">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search name, license or city…"
              className="input pl-7 text-xs h-8"
              style={{ width: 220 }}
            />
          </div>
          <button onClick={openCreate} className="btn-primary px-3 py-1.5 text-xs gap-1.5">
            <Plus size={13} /> Add Lawyer
          </button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-10"><Spinner size={28} /></div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-10 text-sm" style={{ color: 'var(--text-muted)' }}>
            {search ? 'No lawyers match your search.' : 'No lawyers registered yet. Click "Add Lawyer" to start.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Full Name</th>
                  <th>Bar License</th>
                  <th>City</th>
                  <th>Category</th>
                  <th>NGO</th>
                  <th>Available</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(l => (
                  <LawyerRow
                    key={l.lawyer_id}
                    lawyer={l}
                    ngoMap={ngoMap}
                    onEdit={() => openEdit(l)}
                    onDelete={() => setDeleteTarget(l)}
                    onToggleAvailable={() => handleToggleAvailable(l)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create / Edit modal */}
      {modal.open && (
        <LawyerFormModal
          lawyer={modal.lawyer}
          onSave={handleSave}
          onClose={closeModal}
          saving={saving}
          error={formError}
        />
      )}

      {/* Delete confirmation */}
      {deleteTarget && createPortal(
        <div
          className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={e => { if (e.target === e.currentTarget) setDeleteTarget(null) }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="card p-6 max-w-sm w-full"
            style={{ boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
          >
            <div className="text-center mb-4">
              <div className="text-3xl mb-2">🗑️</div>
              <h4 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>Delete Lawyer</h4>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Permanently delete <strong style={{ color: 'var(--text-primary)' }}>{deleteTarget.full_name}</strong>? This cannot be undone.
              </p>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary flex-1 py-2 text-sm justify-center" onClick={() => setDeleteTarget(null)}>
                Cancel
              </button>
              <button
                className="flex-1 py-2 text-sm rounded-xl font-medium flex items-center justify-center gap-1.5 transition-colors"
                style={{ background: '#ef4444', color: '#fff' }}
                onMouseEnter={e => e.currentTarget.style.background = '#dc2626'}
                onMouseLeave={e => e.currentTarget.style.background = '#ef4444'}
                onClick={handleDelete}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          </motion.div>
        </div>,
        document.body
      )}
    </>
  )
}

function LawyerRow({ lawyer: l, ngoMap, onEdit, onDelete, onToggleAvailable }) {
  return (
    <tr>
      <td>
        <div className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{l.full_name}</div>
        <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>{l.lawyer_id}</div>
      </td>
      <td>
        <span className="font-mono text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-muted)' }}>
          {l.bar_license || '—'}
        </span>
      </td>
      <td className="text-xs">{l.city || '—'}</td>
      <td>
        {l.expertise_main ? (
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
            style={{
              background: `${catColor(l.expertise_main)}22`,
              color: catColor(l.expertise_main),
              border: `1px solid ${catColor(l.expertise_main)}44`,
            }}
          >
            {l.expertise_main}
          </span>
        ) : '—'}
      </td>
      <td className="text-xs" style={{ color: 'var(--text-muted)' }}>
        {l.ngo_id && ngoMap[l.ngo_id] ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }}>
            {ngoMap[l.ngo_id]}
          </span>
        ) : '—'}
      </td>
      <td>
        <button
          onClick={onToggleAvailable}
          title={l.available ? 'Click to mark unavailable' : 'Click to mark available'}
          className="flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5 transition-opacity hover:opacity-75"
          style={{
            background: l.available ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.12)',
            color:      l.available ? '#10B981' : '#f87171',
            border:     `1px solid ${l.available ? '#10B98133' : '#ef444433'}`,
          }}
        >
          {l.available ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
          {l.available ? 'Available' : 'Busy'}
        </button>
      </td>
      <td>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Edit"
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: '#f87171' }}
            title="Delete"
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.12)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── Case Routing Tab ──────────────────────────────────────────────────────────

// ── Chart design tokens (shared across DashboardTab + RoutingTab) ─────────────
const CHART_TOOLTIP = {
  contentStyle: {
    background: 'var(--bg-card)',
    border: '1px solid rgba(139,92,246,0.18)',
    borderRadius: 8,
    fontSize: 12,
    boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
  },
  labelStyle: { color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2 },
  itemStyle:  { color: 'var(--text-secondary)' },
  cursor:     { fill: 'rgba(139,92,246,0.06)' },
}
const CHART_TICK   = { fill: 'var(--text-muted)', fontSize: 11 }
const CHART_AXIS   = { axisLine: false, tickLine: false }
const CHART_LEGEND = { wrapperStyle: { fontSize: 11, paddingTop: 8, color: 'var(--text-muted)' } }

// Semantic colors for status pie — matches StatusBadge values
const STATUS_PIE_COLORS = {
  pending:   '#94A3B8',
  in_review: '#818CF8',
  assigned:  '#FBBF24',
  resolved:  '#34D399',
  closed:    '#64748B',
}

const CONF_COLOR  = { High: '#10B981', Medium: '#F59E0B', Low: '#EF4444' }
const CONF_LABEL  = { High: 'NGO + Lawyer matched', Medium: 'One side matched', Low: 'No match' }
const APP_STATUSES = ['pending', 'in_review', 'assigned', 'resolved', 'closed']

function confLevel(ngoId, lawyerId) {
  return ngoId && lawyerId ? 'High' : (ngoId || lawyerId) ? 'Medium' : 'Low'
}

function ConfidenceBadge({ ngoId, lawyerId }) {
  const level = confLevel(ngoId, lawyerId)
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold"
      style={{ background: `${CONF_COLOR[level]}1a`, color: CONF_COLOR[level] }}
    >
      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: CONF_COLOR[level] }} />
      {level}
    </span>
  )
}

// ── Routing Manage Modal ──────────────────────────────────────────────────────

function RoutingManageModal({ app, ngos, lawyers, onClose, onUpdate }) {
  const { theme } = useAppStore()
  const isDark = theme === 'dark'

  const borderColor  = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.09)'
  const sectionBg    = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)'

  const [ngoSel,    setNgoSel]    = useState('')
  const [lawSel,    setLawSel]    = useState('')
  const [statusSel, setStatusSel] = useState(app.status)

  const [savingNgo,    setSavingNgo]    = useState(false)
  const [savingLaw,    setSavingLaw]    = useState(false)
  const [savingStatus, setSavingStatus] = useState(false)
  const [rerouting,    setRerouting]    = useState(false)
  const [toast,        setToast]        = useState('')

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 2200) }

  const handleAssignNgo = async () => {
    if (!ngoSel) return
    setSavingNgo(true)
    try {
      await assignNGO(app.application_id, ngoSel)
      showToast('NGO assigned successfully')
      onUpdate()
      setNgoSel('')
    } catch { showToast('Failed to assign NGO') }
    setSavingNgo(false)
  }

  const handleAssignLaw = async () => {
    if (!lawSel) return
    setSavingLaw(true)
    try {
      await assignLawyer(app.application_id, lawSel)
      showToast('Lawyer assigned successfully')
      onUpdate()
      setLawSel('')
    } catch { showToast('Failed to assign lawyer') }
    setSavingLaw(false)
  }

  const handleStatus = async () => {
    if (statusSel === app.status) return
    setSavingStatus(true)
    try {
      await updateApplicationStatus(app.application_id, statusSel)
      showToast('Status updated')
      onUpdate()
    } catch { showToast('Failed to update status') }
    setSavingStatus(false)
  }

  const handleReroute = async () => {
    setRerouting(true)
    try {
      await rerouteApplication(app.application_id)
      showToast('Routing updated automatically')
      onUpdate()
    } catch { showToast('Re-routing failed') }
    setRerouting(false)
  }

  const lawyerName = app.suggested_lawyer ? app.suggested_lawyer.split('(')[0].trim() : ''
  const level      = confLevel(app.assigned_ngo_id, app.assigned_lawyer_id)
  const inputCls   = 'input text-sm'

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: 8 }}
        transition={{ duration: 0.18 }}
        className="card w-full flex flex-col"
        style={{ maxWidth: 980, maxHeight: '90vh', padding: 0, boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.07)' }}
      >
        {/* ── Header ── */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b shrink-0"
          style={{ borderColor }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: 'linear-gradient(135deg,#7C3AED,#3B82F6)' }}
            >
              <Settings2 size={14} color="#fff" />
            </div>
            <div>
              <div className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                Case Routing Management
              </div>
              <div className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                {app.application_id}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <AnimatePresence>
              {toast && (
                <motion.span
                  key="toast"
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="text-xs font-medium px-3 py-1 rounded-full"
                  style={{ background: 'rgba(16,185,129,0.15)', color: '#34D399' }}
                >
                  {toast}
                </motion.span>
              )}
            </AnimatePresence>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Body: two-column grid ── */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 min-h-full" style={{ borderColor }}>

            {/* ════ LEFT COLUMN — Case context ════ */}
            <div
              className="px-6 py-6 space-y-6 border-b md:border-b-0 md:border-r"
              style={{ borderColor }}
            >
              {/* Applicant block */}
              <div>
                <div className="label mb-3">Applicant</div>
                <div className="space-y-2">
                  <div className="flex items-baseline gap-2">
                    <span dir="auto" className="font-semibold text-base" style={{ color: 'var(--text-primary)' }}>{app.name}</span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{app.city}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="px-2 py-0.5 rounded text-[11px] font-medium"
                      style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-secondary)', border: '1px solid rgba(255,255,255,0.10)' }}
                    >
                      {app.case_type}
                    </span>
                    <RiskBadge level={app.urgency?.toLowerCase()} />
                    <StatusBadge status={app.status} />
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ height: 1, background: borderColor }} />

              {/* Routing summary */}
              <div>
                <div className="label mb-3">Routing Summary</div>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <ConfidenceBadge ngoId={app.assigned_ngo_id} lawyerId={app.assigned_lawyer_id} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {CONF_LABEL[level]}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>NGO</div>
                      {app.assigned_ngo ? (
                        <span className="text-xs font-medium" style={{ color: '#10B981' }}>{app.assigned_ngo}</span>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Unassigned</span>
                      )}
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>Lawyer</div>
                      {lawyerName ? (
                        <span className="text-xs font-medium" style={{ color: '#60A5FA' }}>{lawyerName}</span>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Unassigned</span>
                      )}
                    </div>
                  </div>
                  {app.notes ? (
                    <p
                      className="text-[12px] leading-relaxed pt-1"
                      style={{ color: 'var(--text-secondary)', borderLeft: '2px solid rgba(124,58,237,0.4)', paddingLeft: 10 }}
                    >
                      {app.notes}
                    </p>
                  ) : (
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No routing note recorded.</p>
                  )}
                </div>
              </div>

              {/* Divider */}
              <div style={{ height: 1, background: borderColor }} />

              {/* Re-route — secondary action, lives in the context column */}
              <div>
                <div className="label mb-2">Automatic Routing</div>
                <p className="text-[11px] mb-3" style={{ color: 'var(--text-muted)' }}>
                  Re-apply the scoring engine to find the best available NGO and lawyer. Overwrites current assignments.
                </p>
                <button
                  onClick={handleReroute}
                  disabled={rerouting}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-colors w-full justify-center"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.10)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)' }}
                >
                  {rerouting ? <Spinner size={13} /> : <RefreshCw size={13} />}
                  Re-run Automatic Routing
                </button>
              </div>
            </div>

            {/* ════ RIGHT COLUMN — Actions ════ */}
            <div className="px-6 py-6 space-y-6">

              {/* Assignments section */}
              <div>
                <div className="label mb-4">Assignments</div>

                {/* NGO */}
                <div className="space-y-2 mb-5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>NGO</span>
                    {app.assigned_ngo && (
                      <span
                        className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                        style={{ background: 'rgba(16,185,129,0.12)', color: '#10B981' }}
                      >
                        {app.assigned_ngo}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <select
                      className="input text-sm flex-1"
                      value={ngoSel}
                      onChange={e => setNgoSel(e.target.value)}
                    >
                      <option value="">— Select NGO —</option>
                      {ngos.filter(n => n.active !== false).map(n => (
                        <option key={n.ngo_id} value={n.ngo_id}>{n.ngo_name} · {n.city}</option>
                      ))}
                    </select>
                    <button
                      onClick={handleAssignNgo}
                      disabled={!ngoSel || savingNgo}
                      className="btn-primary px-4 py-2 text-xs shrink-0"
                      style={{ opacity: !ngoSel ? 0.45 : 1 }}
                    >
                      {savingNgo ? <Spinner size={13} /> : 'Assign'}
                    </button>
                  </div>
                </div>

                {/* Divider */}
                <div className="mb-5" style={{ height: 1, background: borderColor }} />

                {/* Lawyer */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Lawyer</span>
                    {lawyerName && (
                      <span
                        className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                        style={{ background: 'rgba(59,130,246,0.12)', color: '#60A5FA' }}
                      >
                        {lawyerName}
                        {app.suggested_lawyer?.match(/\(([^)]+)\)/)?.[1]
                          ? <span style={{ opacity: 0.65 }}> · {app.suggested_lawyer.match(/\(([^)]+)\)/)[1]}</span>
                          : null}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <select
                      className="input text-sm flex-1"
                      value={lawSel}
                      onChange={e => setLawSel(e.target.value)}
                    >
                      <option value="">— Select lawyer —</option>
                      {lawyers.filter(l => l.available).map(l => (
                        <option key={l.lawyer_id} value={l.lawyer_id}>
                          {l.full_name} · {l.bar_license} · {l.city}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={handleAssignLaw}
                      disabled={!lawSel || savingLaw}
                      className="btn-primary px-4 py-2 text-xs shrink-0"
                      style={{ opacity: !lawSel ? 0.45 : 1 }}
                    >
                      {savingLaw ? <Spinner size={13} /> : 'Assign'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ height: 1, background: borderColor }} />

              {/* Status */}
              <div>
                <div className="label mb-4">Case Status</div>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Current</span>
                  <StatusBadge status={app.status} />
                </div>
                <div className="flex gap-2">
                  <select
                    className="input text-sm flex-1"
                    value={statusSel}
                    onChange={e => setStatusSel(e.target.value)}
                  >
                    {APP_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <button
                    onClick={handleStatus}
                    disabled={statusSel === app.status || savingStatus}
                    className="btn-primary px-4 py-2 text-xs shrink-0"
                    style={{ opacity: statusSel === app.status ? 0.45 : 1 }}
                  >
                    {savingStatus ? <Spinner size={13} /> : 'Update'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body
  )
}

// ── Clean routing table row ───────────────────────────────────────────────────

function RoutingRow({ app, onManage }) {
  const lawyerName = app.suggested_lawyer ? app.suggested_lawyer.split('(')[0].trim() : ''

  return (
    <tr
      className="group cursor-pointer"
      onClick={onManage}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <td className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
        {app.application_id?.slice(-8)}
      </td>
      <td>
        <div dir="auto" className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{app.name}</div>
        <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{app.city}</div>
      </td>
      <td>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{app.case_type}</span>
      </td>
      <td><RiskBadge level={app.urgency?.toLowerCase()} /></td>
      <td><StatusBadge status={app.status} /></td>
      <td>
        <ConfidenceBadge ngoId={app.assigned_ngo_id} lawyerId={app.assigned_lawyer_id} />
      </td>
      <td>
        {app.assigned_ngo ? (
          <span className="text-xs font-medium" style={{ color: '#10B981' }}>{app.assigned_ngo}</span>
        ) : (
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>—</span>
        )}
      </td>
      <td>
        {lawyerName ? (
          <span className="text-xs font-medium" style={{ color: '#60A5FA' }}>{lawyerName}</span>
        ) : (
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>—</span>
        )}
      </td>
      <td onClick={e => e.stopPropagation()}>
        <button
          onClick={onManage}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors"
          style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.12)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
        >
          <Settings2 size={12} />
          Manage
        </button>
      </td>
    </tr>
  )
}

// ── Routing Tab ───────────────────────────────────────────────────────────────

const ROUTING_FILTERS = [
  { key: 'all',       label: 'All' },
  { key: 'unrouted',  label: 'Unrouted' },
  { key: 'pending',   label: 'Pending' },
  { key: 'assigned',  label: 'Assigned' },
  { key: 'in_review', label: 'In Review' },
  { key: 'resolved',  label: 'Resolved' },
]

function RoutingTab() {
  const [apps, setApps]           = useState([])
  const [ngos, setNgos]           = useState([])
  const [lawyers, setLawyers]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [filter, setFilter]       = useState('all')
  const [managingApp, setManagingApp] = useState(null)
  const { theme } = useAppStore()
  const isDark = theme === 'dark'

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [appData, ngoData, lawData] = await Promise.all([
        getApplications({ limit: 500 }),
        getNGOs(),
        getLawyers(),
      ])
      setApps(appData.applications || [])
      setNgos(ngoData.ngos || [])
      setLawyers(lawData.lawyers || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleUpdate = useCallback(async () => {
    const [appData] = await Promise.all([getApplications({ limit: 500 })])
    const updated = appData.applications || []
    setApps(updated)
    if (managingApp) {
      const fresh = updated.find(a => a.application_id === managingApp.application_id)
      if (fresh) setManagingApp(fresh)
    }
  }, [managingApp])

  const filtered = filter === 'all'
    ? apps
    : filter === 'unrouted'
    ? apps.filter(a => !a.assigned_ngo_id && !a.assigned_lawyer_id)
    : apps.filter(a => a.status === filter)

  const countFor = (key) =>
    key === 'all'      ? apps.length
    : key === 'unrouted' ? apps.filter(a => !a.assigned_ngo_id && !a.assigned_lawyer_id).length
    : apps.filter(a => a.status === key).length

  if (loading) return <div className="flex justify-center py-12"><Spinner size={32} /></div>

  return (
    <div className="space-y-4">
      {/* Filter + legend row */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1.5 flex-wrap">
          {ROUTING_FILTERS.map(f => {
            const active = filter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: active ? '#7C3AED' : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                  color: active ? '#fff' : 'var(--text-secondary)',
                }}
              >
                {f.label}
                <span className="ml-1.5 opacity-60">({countFor(f.key)})</span>
              </button>
            )
          })}
        </div>
        <div className="ml-auto flex items-center gap-4 text-[11px]" style={{ color: 'var(--text-muted)' }}>
          {Object.entries(CONF_COLOR).map(([k, c]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: c }} />
              {k}
            </span>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card padding="p-0">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Applicant</th>
                <th>Case Type</th>
                <th>Urgency</th>
                <th>Status</th>
                <th>Confidence</th>
                <th style={{ color: '#10B981' }}>NGO</th>
                <th style={{ color: '#60A5FA' }}>Lawyer</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(app => (
                <RoutingRow
                  key={app.application_id}
                  app={app}
                  onManage={() => setManagingApp(app)}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-10" style={{ color: 'var(--text-muted)' }}>
                    No applications for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Routing Manage Modal */}
      <AnimatePresence>
        {managingApp && (
          <RoutingManageModal
            key={managingApp.application_id}
            app={managingApp}
            ngos={ngos}
            lawyers={lawyers}
            onClose={() => setManagingApp(null)}
            onUpdate={handleUpdate}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Analytics Tab ─────────────────────────────────────────────────────────────
function AnalyticsTab() {
  return <div dir="ltr"><AnalyticsPage /></div>
}

// ── Main Admin Page ───────────────────────────────────────────────────────────
export default function AdminPage() {
  const { adminAuthenticated, setAdminAuth } = useAppStore()

  if (!adminAuthenticated) {
    return <AdminLoginGate onLogin={setAdminAuth} />
  }

  return (
    <PageContainer size="full" dir="ltr">
      <SectionHeader eyebrow="Administration" title="Admin Dashboard" />
      <AdminNav />
      <Routes>
        <Route index element={<DashboardTab />} />
        <Route path="ngos" element={<NGOTab />} />
        <Route path="lawyers" element={<LawyersTab />} />
        <Route path="analytics" element={<AnalyticsTab />} />
        <Route path="routing" element={<RoutingTab />} />
      </Routes>
    </PageContainer>
  )
}

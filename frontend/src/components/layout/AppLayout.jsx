import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Scale, MessageSquare, FileText, AlertTriangle, Info,
  LayoutDashboard, BarChart3, Building2, Users, Menu, X,
  ChevronRight, Settings, Globe, MapPin, LogOut, Sun, Moon, FileSearch,
} from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL } from '@/services/i18n'
import ScalesIcon from '@/components/ui/ScalesIcon'
import CitySelector from '@/components/ui/CitySelector'
import LanguageSelector from '@/components/ui/LanguageSelector'
import AIAssistantDrawer from '@/components/chat/AIAssistantDrawer'
import FloatingAIButton from '@/components/ui/FloatingAIButton'

const NAV = [
  { href: '/home',              icon: LayoutDashboard, key: 'nav_home',              group: 'main' },
  { action: 'openAiDrawer',    icon: MessageSquare,   key: 'nav_chat',              group: 'main' },
  { href: '/document-analysis', icon: FileSearch,     key: 'nav_document_analysis', group: 'main' },
  { href: '/apply',             icon: FileText,        key: 'nav_apply',             group: 'main' },
  { href: '/lawyers',           icon: Users,           key: 'nav_lawyers',           group: 'main' },
  { href: '/ngos',              icon: Building2,       key: 'nav_ngos',              group: 'main' },
  { href: '/emergency',         icon: AlertTriangle,   key: 'nav_emergency',         group: 'main' },
  { href: '/about',             icon: Info,            key: 'nav_about',             group: 'main' },
  { href: '/admin',             icon: Settings,        key: 'nav_admin',             group: 'admin' },
]

export default function AppLayout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const t = useT()
  const { language, city, sidebarOpen, toggleSidebar, adminAuthenticated, clearAdminAuth, theme, toggleTheme, toggleAiDrawer } = useAppStore()

  const handleNavAction = (action) => {
    if (action === 'openAiDrawer') toggleAiDrawer()
  }
  const rtl = isRTL(language)
  const isDark = theme === 'dark'
  const isAdminRoute = location.pathname.startsWith('/admin')

  const mainNav  = NAV.filter(n => n.group === 'main')
  const adminNav = NAV.filter(n => n.group === 'admin')

  return (
    // Outer shell is always LTR — sidebar must never mirror to the right
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-page)' }}>

      {/* ── Sidebar ── always anchored left, unaffected by language direction */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            initial={{ x: -242 }}
            animate={{ x: 0 }}
            exit={{ x: -242 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="sidebar z-40"
            style={{ left: 0 }}
          >
            {/* Logo */}
            <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.09)' }}>
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{
                  background: 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
                  boxShadow: isDark
                    ? '0 0 0 1px rgba(124,58,237,0.45), 0 0 16px rgba(124,58,237,0.50), 0 0 32px rgba(59,130,246,0.22)'
                    : '0 0 0 1px rgba(124,58,237,0.22), 0 2px 8px rgba(124,58,237,0.10)',
                }}
              >
                <ScalesIcon size={22} gid="al" />
              </div>
              <div>
                <div className="text-sm font-bold leading-tight" style={{ color: isDark ? '#F1F5F9' : '#0F172A' }}>Pakistan AI</div>
                <div className="text-[11px]" style={{ color: isDark ? 'rgba(255,255,255,0.32)' : 'rgba(15,23,42,0.45)' }}>Legal Aid · RAG + Groq</div>
              </div>
            </div>

            {/* Nav */}
            <nav className="flex-1 overflow-y-auto p-3 space-y-5">
              <div>
                <div
                  className="text-[9px] font-bold uppercase tracking-widest px-2 mb-2"
                  style={{ color: isDark ? 'rgba(255,255,255,0.20)' : 'rgba(15,23,42,0.35)' }}
                >
                  Main
                </div>
                {mainNav.map(item => (
                  <NavItem key={item.href || item.action} item={item} current={location.pathname} t={t} onAction={handleNavAction} />
                ))}
              </div>

              <div>
                <div
                  className="text-[9px] font-bold uppercase tracking-widest px-2 mb-2"
                  style={{ color: isDark ? 'rgba(255,255,255,0.20)' : 'rgba(15,23,42,0.35)' }}
                >
                  System
                </div>
                {adminNav.map(item => (
                  <NavItem key={item.href || item.action} item={item} current={location.pathname} t={t} onAction={handleNavAction} />
                ))}
              </div>
            </nav>

            {/* Bottom controls */}
            <div className="p-3 border-t space-y-2" style={{ borderColor: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.09)' }}>
              <LanguageSelector compact />
              <CitySelector compact />
              {adminAuthenticated && (
                <button
                  onClick={() => { clearAdminAuth(); navigate('/home') }}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-xs transition-colors"
                  style={{ color: '#f87171' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.10)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <LogOut size={13} /> Logout Admin
                </button>
              )}
              <div className="px-2 pt-1 text-[10px] leading-relaxed" style={{ color: isDark ? 'rgba(255,255,255,0.20)' : 'rgba(15,23,42,0.38)' }}>
                🔒 Private · No data stored · Free to use
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* ── AI Assistant Drawer + Floating Button ── */}
      <AIAssistantDrawer />
      {!location.pathname.startsWith('/admin') && <FloatingAIButton />}

      {/* ── Main Content ── always pushed right of the left sidebar */}
      <div
        className="flex-1 flex flex-col h-full transition-all duration-300"
        style={{ marginLeft: sidebarOpen ? 242 : 0 }}
      >
        {/* Topbar — always LTR: hamburger left, breadcrumb center-left, pills right */}
        <header
          dir="ltr"
          className="sticky top-0 z-30 flex items-center px-4 gap-3"
          style={{
            height: 52,
            background: isDark ? 'rgba(7,13,26,0.82)' : 'rgba(248,250,252,0.90)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderBottom: isDark
              ? '1px solid rgba(255,255,255,0.07)'
              : '1px solid rgba(0,0,0,0.08)',
          }}
        >
          {/* Sidebar toggle */}
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-xl transition-all duration-150 flex-shrink-0"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => {
              e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'
              e.currentTarget.style.color = 'var(--text-primary)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'var(--text-muted)'
            }}
          >
            {sidebarOpen ? <X size={17} /> : <Menu size={17} />}
          </button>

          <Breadcrumb pathname={location.pathname} t={t} isDark={isDark} />

          {/* Right side */}
          <div className="ml-auto flex items-center gap-2">
            {adminAuthenticated && (
              <span className="badge badge-success text-[10px]">Admin</span>
            )}

            {/* Language + city pills */}
            <span
              className="text-[11px] font-mono px-2 py-1 rounded-lg"
              style={{
                color: 'var(--text-muted)',
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
              }}
            >
              {language === 'Urdu' ? 'اردو' : 'EN'}
            </span>
            {city && (
              <span
                className="text-[11px] px-2 py-1 rounded-lg"
                style={{
                  color: 'var(--text-muted)',
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                }}
              >
                📍 {city}
              </span>
            )}

            {/* ── Theme Toggle ── */}
            <motion.button
              onClick={toggleTheme}
              whileTap={{ scale: 0.90 }}
              className="relative p-2 rounded-xl transition-all duration-200 flex-shrink-0 overflow-hidden"
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              style={{
                color: isDark ? '#FCD34D' : '#7C3AED',
                background: isDark ? 'rgba(252,211,77,0.10)' : 'rgba(124,58,237,0.10)',
                border: isDark ? '1px solid rgba(252,211,77,0.20)' : '1px solid rgba(124,58,237,0.20)',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = isDark ? 'rgba(252,211,77,0.18)' : 'rgba(124,58,237,0.18)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = isDark ? 'rgba(252,211,77,0.10)' : 'rgba(124,58,237,0.10)'
              }}
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={theme}
                  initial={{ rotate: -30, opacity: 0, scale: 0.7 }}
                  animate={{ rotate: 0,   opacity: 1, scale: 1   }}
                  exit={{    rotate:  30, opacity: 0, scale: 0.7 }}
                  transition={{ duration: 0.20 }}
                  className="flex items-center justify-center"
                >
                  {isDark ? <Sun size={16} /> : <Moon size={16} />}
                </motion.span>
              </AnimatePresence>
            </motion.button>
          </div>
        </header>

        {/* Page content — RTL applied here for Urdu, never on admin routes */}
        <main className="flex-1 overflow-auto" style={{ background: 'var(--bg-page)' }}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
            className="h-full"
            dir={rtl && !isAdminRoute ? 'rtl' : 'ltr'}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

function NavItem({ item, current, t, onAction }) {
  if (item.action) {
    return (
      <button onClick={() => onAction?.(item.action)} className="nav-item w-full text-left">
        <item.icon size={14} className="flex-shrink-0" />
        <span>{t(item.key)}</span>
        <span
          className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-md"
          style={{ background: 'rgba(124,58,237,0.20)', color: '#a78bfa', border: '1px solid rgba(124,58,237,0.28)' }}
        >
          AI
        </span>
      </button>
    )
  }

  const active = current === item.href || (item.href !== '/home' && current.startsWith(item.href))
  return (
    <Link to={item.href} className={`nav-item ${active ? 'active' : ''}`}>
      <item.icon size={14} className="flex-shrink-0" />
      <span>{t(item.key)}</span>
      {active && <ChevronRight size={11} className="ml-auto opacity-50" />}
    </Link>
  )
}

function Breadcrumb({ pathname, t, isDark }) {
  const segments = pathname.split('/').filter(Boolean)
  const isHome = segments.length === 0 || segments[0] === 'home'
  const mutedColor = isDark ? 'rgba(255,255,255,0.38)' : 'rgba(15,23,42,0.45)'
  const hoverStyle = isDark ? 'hover:text-white' : 'hover:text-slate-900'

  if (isHome) return (
    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
      {t('nav_home')}
    </span>
  )

  const label = {
    chat: t('nav_chat'), apply: t('nav_apply'), emergency: t('nav_emergency'),
    about: t('nav_about'), admin: t('nav_admin'), analytics: t('nav_analytics'),
    ngos: t('nav_ngos'), lawyers: t('nav_lawyers'),
    'document-analysis': t('nav_document_analysis'),
  }[segments[0]] || segments[0]

  return (
    <div className="flex items-center gap-1.5 text-sm" style={{ color: mutedColor }}>
      <Link
        to="/home"
        className={`transition-colors ${hoverStyle}`}
        style={{ color: mutedColor }}
      >
        Home
      </Link>
      <ChevronRight size={11} style={{ color: mutedColor }} />
      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{label}</span>
    </div>
  )
}

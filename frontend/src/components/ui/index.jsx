import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { useAppStore } from '@/services/store'

// ── Badge ─────────────────────────────────────────────────────────────────────
export function Badge({ children, variant = 'neutral', className, ...props }) {
  return (
    <span className={clsx('badge', `badge-${variant}`, className)} {...props}>
      {children}
    </span>
  )
}

const BADGE_BASE = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '2px 8px', borderRadius: 5,
  fontSize: 11, fontWeight: 500, letterSpacing: 0.1, whiteSpace: 'nowrap',
}
function Dot({ color }) {
  return <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0 }} />
}

export function RiskBadge({ level }) {
  const map = {
    low:      { color: '#22C55E', bg: 'rgba(34,197,94,0.10)',   label: 'Low' },
    medium:   { color: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  label: 'Medium' },
    high:     { color: '#F87171', bg: 'rgba(239,68,68,0.10)',   label: 'High' },
    critical: { color: '#EF4444', bg: 'rgba(239,68,68,0.13)',   label: 'Critical' },
  }
  const { color, bg, label } = map[(level || '').toLowerCase()] || map.low
  return <span style={{ ...BADGE_BASE, background: bg, color }}><Dot color={color} />{label}</span>
}

export function StatusBadge({ status }) {
  const map = {
    pending:   { color: '#94A3B8', bg: 'rgba(148,163,184,0.10)', label: 'Pending' },
    in_review: { color: '#818CF8', bg: 'rgba(129,140,248,0.10)', label: 'In Review' },
    assigned:  { color: '#FBBF24', bg: 'rgba(251,191,36,0.10)',  label: 'Assigned' },
    resolved:  { color: '#34D399', bg: 'rgba(52,211,153,0.10)',  label: 'Resolved' },
    closed:    { color: '#64748B', bg: 'rgba(100,116,139,0.10)', label: 'Closed' },
  }
  const { color, bg, label } = map[status] || { color: '#94A3B8', bg: 'rgba(148,163,184,0.08)', label: status || '—' }
  return <span style={{ ...BADGE_BASE, background: bg, color }}><Dot color={color} />{label}</span>
}

// ── Card ──────────────────────────────────────────────────────────────────────
export function Card({ children, className, padding = 'p-5', ...props }) {
  return (
    <div className={clsx('card', padding, className)} {...props}>
      {children}
    </div>
  )
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
export function KPICard({ label, value, sub, subColor, icon, accent }) {
  return (
    <div className="kpi-card">
      <div className="flex items-start justify-between">
        <div>
          <div className="label">{label}</div>
          <div className="font-display text-2xl font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
            {value}
          </div>
          {sub && (
            <div className="text-xs mt-1" style={{ color: subColor || 'var(--text-muted)' }}>
              {sub}
            </div>
          )}
        </div>
        {icon && (
          <div className="text-2xl opacity-60">{icon}</div>
        )}
      </div>
      {accent && (
        <div className="mt-3 h-0.5 rounded-full" style={{ background: accent, opacity: 0.4 }} />
      )}
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
export function Skeleton({ className, ...props }) {
  return <div className={clsx('shimmer rounded-md', className)} {...props} />
}

export function CardSkeleton() {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  )
}

// ── Alert ─────────────────────────────────────────────────────────────────────
export function Alert({ type = 'info', children, className }) {
  const isDark = useAppStore(s => s.theme === 'dark')
  const styles = {
    info:    { bg: 'rgba(79,142,247,.07)',  border: 'rgba(79,142,247,.2)',  color: isDark ? '#93c5fd' : '#1d4ed8' },
    success: { bg: 'rgba(52,199,123,.07)', border: 'rgba(52,199,123,.2)', color: isDark ? '#6ee7b7' : '#15803d' },
    warning: { bg: 'rgba(251,191,36,.07)', border: 'rgba(251,191,36,.2)', color: isDark ? '#fcd34d' : '#b45309' },
    danger:  { bg: 'rgba(240,68,68,.07)',  border: 'rgba(240,68,68,.2)',  color: isDark ? '#f87171' : '#b91c1c' },
  }
  const s = styles[type] || styles.info
  return (
    <div
      className={clsx('flex gap-3 items-start rounded-lg border p-3 text-sm leading-relaxed', className)}
      style={{ background: s.bg, borderColor: s.border, color: s.color }}
    >
      {children}
    </div>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="animate-spin">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────
export function Divider({ className }) {
  return <hr className={clsx('my-4', className)} style={{ borderColor: 'var(--border-default)' }} />
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function EmptyState({ icon, title, description, action }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 text-center px-4"
    >
      {icon && <div className="text-5xl mb-4 opacity-60">{icon}</div>}
      <p className="font-semibold text-lg mb-2" style={{ color: 'var(--text-primary)' }}>{title}</p>
      {description && <p className="text-sm max-w-xs" style={{ color: 'var(--text-muted)' }}>{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </motion.div>
  )
}

// ── Progress bar ──────────────────────────────────────────────────────────────
export function ProgressBar({ value, max = 100, color = 'var(--primary)', height = 6 }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className="w-full rounded-full overflow-hidden" style={{ height, background: 'var(--neutral-100)' }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="h-full rounded-full"
        style={{ background: color }}
      />
    </div>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
export function SectionHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        {eyebrow && <div className="section-eyebrow">{eyebrow}</div>}
        <h1 className="section-title">{title}</h1>
        {description && (
          <p className="mt-1 text-sm max-w-xl" style={{ color: 'var(--text-muted)' }}>{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}

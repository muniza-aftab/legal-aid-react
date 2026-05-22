import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { Search, MapPin, Building2, Scale } from 'lucide-react'
import { getLawyers, getNGOs } from '@/services/api'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { useAppStore } from '@/services/store'
import { SectionHeader, Spinner, Card } from '@/components/ui/index'
import { PageContainer } from '@/components/layout/PageLayout'

const CITIES = [
  '', 'Karachi', 'Lahore', 'Islamabad', 'Rawalpindi',
  'Peshawar', 'Quetta', 'Multan', 'Faisalabad',
]

const EXPERTISE_LIST = [
  '', 'Family Law', 'Criminal Law', 'Labour Law', 'Property Law',
  'Inheritance Law', 'Cybercrime', 'Harassment', 'Civil Law / Procedure',
  'Contract Law', 'Consumer Rights', 'Constitutional Law', 'General / Other',
]

const CAT_COLOR = {
  'Family Law':           '#EC4899',
  'Criminal Law':         '#EF4444',
  'Labour Law':           '#F59E0B',
  'Property Law':         '#8B5CF6',
  'Inheritance Law':      '#7C3AED',
  'Cybercrime':           '#06B6D4',
  'Harassment':           '#F97316',
  'Civil Law / Procedure':'#3B82F6',
  'Contract Law':         '#10B981',
  'Consumer Rights':      '#84CC16',
  'Constitutional Law':   '#6366F1',
  'General / Other':      '#64748B',
}

const AVATAR_COLORS = [
  '#7C3AED','#6366F1','#3B82F6','#10B981',
  '#F59E0B','#EF4444','#EC4899','#8B5CF6',
]

function avatarColor(name = '') {
  const hash = name.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?'
}

function catColor(expertise) {
  return CAT_COLOR[expertise] || '#64748B'
}

function AvailDot({ available }) {
  const t = useT()
  const color = available ? '#34D399' : '#64748B'
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 11, fontWeight: 500, color,
        background: available ? 'rgba(52,211,153,0.10)' : 'rgba(100,116,139,0.10)',
        padding: '2px 7px', borderRadius: 5, whiteSpace: 'nowrap', flexShrink: 0,
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color }} />
      {available ? t('lawyers_available') : t('lawyers_busy')}
    </span>
  )
}

function ExpertiseChip({ label }) {
  const { language } = useAppStore()
  const color = catColor(label)
  return (
    <span
      style={{
        display: 'inline-block', fontSize: 11, fontWeight: 500,
        color, background: `${color}18`,
        padding: '2px 7px', borderRadius: 5, whiteSpace: 'nowrap',
      }}
    >
      {translateCategory(label, language)}
    </span>
  )
}

function CityChip({ label }) {
  return (
    <span
      className="inline-flex items-center gap-1"
      style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}
    >
      <MapPin size={10} />
      {label}
    </span>
  )
}

function LawyerCard({ lawyer, ngoName, index }) {
  const bg    = avatarColor(lawyer.full_name)
  const inits = initials(lawyer.full_name)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, delay: index * 0.03 }}
      whileHover={{ scale: 1.015, y: -2 }}
      className="card p-4 flex gap-3"
      style={{ alignItems: 'flex-start' }}
    >
      <div
        className="flex-shrink-0 flex items-center justify-center rounded-lg font-bold text-white text-sm"
        style={{ width: 36, height: 36, background: bg, letterSpacing: 0.5 }}
      >
        {inits}
      </div>

      {/* Content — LTR: names, license numbers, city are English data */}
      <div className="flex-1 min-w-0" dir="ltr">
        <div className="flex items-center justify-between gap-2 mb-0.5">
          <span className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
            {lawyer.full_name}
          </span>
          <AvailDot available={lawyer.available} />
        </div>

        <div className="font-mono text-[11px] mb-2.5" style={{ color: 'var(--text-muted)', letterSpacing: 0.3 }}>
          {lawyer.bar_license}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {lawyer.expertise_main && <ExpertiseChip label={lawyer.expertise_main} />}
          {lawyer.city           && <CityChip label={lawyer.city} />}
        </div>

        {ngoName && (
          <div className="flex items-center gap-1 mt-2 text-[11px]" style={{ color: 'var(--text-muted)' }}>
            <Building2 size={10} style={{ flexShrink: 0 }} />
            <span>{ngoName}</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default function LawyersPage() {
  const t = useT()
  const { theme, language } = useAppStore()
  const rtl = isRTL(language)
  const isDark = theme === 'dark'

  const [lawyers,   setLawyers]   = useState([])
  const [ngoMap,    setNgoMap]    = useState({})
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [city,      setCity]      = useState('')
  const [expertise, setExpertise] = useState('')
  const [availOnly, setAvailOnly] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([getLawyers(), getNGOs()])
      .then(([lData, nData]) => {
        setLawyers(lData.lawyers || [])
        const map = {}
        for (const n of (nData.ngos || [])) map[n.ngo_id] = n.ngo_name
        setNgoMap(map)
      })
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return lawyers.filter(l => {
      if (availOnly && !l.available) return false
      if (city      && l.city !== city) return false
      if (expertise && l.expertise_main !== expertise) return false
      if (q && !(
        l.full_name?.toLowerCase().includes(q) ||
        l.bar_license?.toLowerCase().includes(q) ||
        l.expertise_main?.toLowerCase().includes(q) ||
        l.city?.toLowerCase().includes(q)
      )) return false
      return true
    })
  }, [lawyers, search, city, expertise, availOnly])

  const availCount = lawyers.filter(l => l.available).length

  const inputBg    = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'
  const pillActive = { background: '#7C3AED', color: '#fff' }
  const pillIdle   = {
    background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
    color: 'var(--text-secondary)',
  }

  return (
    <PageContainer size="wide">
      <SectionHeader
        eyebrow={t('lawyers_eyebrow')}
        title={t('lawyers_title')}
        description={t('lawyers_sub')}
      />

      {/* ── Filter bar ── */}
      <Card padding="px-4 py-3" className="mb-5 flex items-center gap-2 flex-wrap">
        <div className="relative" style={{ flex: '1 1 200px', minWidth: 160 }}>
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: 'var(--text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('lawyers_search_ph')}
            className="input pl-8 text-sm"
            style={{ background: inputBg }}
          />
        </div>

        <select
          value={city}
          onChange={e => setCity(e.target.value)}
          className="input text-sm"
          style={{ background: inputBg, flex: '0 1 140px' }}
        >
          {CITIES.map(c => <option key={c} value={c}>{c || t('lawyers_all_cities')}</option>)}
        </select>

        <select
          value={expertise}
          onChange={e => setExpertise(e.target.value)}
          className="input text-sm"
          style={{ background: inputBg, flex: '0 1 170px' }}
        >
          {EXPERTISE_LIST.map(e => (
            <option key={e} value={e}>{e ? translateCategory(e, language) : t('lawyers_all_exp')}</option>
          ))}
        </select>

        <button
          onClick={() => setAvailOnly(v => !v)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors whitespace-nowrap"
          style={availOnly ? pillActive : pillIdle}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: availOnly ? '#fff' : '#34D399' }} />
          {t('lawyers_avail_only')}
        </button>

        <span className="ml-auto text-xs whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
          {filtered.length} {t('lawyers_of')} {lawyers.length}
          {availCount > 0 && (
            <span style={{ color: '#34D399' }}> · {availCount} {t('lawyers_avail')}</span>
          )}
        </span>
      </Card>

      {/* ── Content ── */}
      {loading ? (
        <div className="flex justify-center py-16"><Spinner size={32} /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <div className="flex justify-center mb-4">
            <Scale size={36} style={{ color: 'rgba(139,92,246,0.32)' }} />
          </div>
          <div className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{t('lawyers_not_found')}</div>
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('lawyers_adjust')}</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((lawyer, i) => (
            <LawyerCard
              key={lawyer.lawyer_id || i}
              lawyer={lawyer}
              ngoName={lawyer.ngo_id ? ngoMap[lawyer.ngo_id] : null}
              index={i}
            />
          ))}
        </div>
      )}
    </PageContainer>
  )
}

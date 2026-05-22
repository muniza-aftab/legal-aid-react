import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Search, Phone, Mail, Building2 } from 'lucide-react'
import { getNGOs } from '@/services/api'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { useAppStore } from '@/services/store'
import { SectionHeader, Card, Badge, Spinner, EmptyState } from '@/components/ui/index'
import { PageContainer } from '@/components/layout/PageLayout'

const CITIES = [
  'Karachi', 'Lahore', 'Islamabad', 'Rawalpindi',
  'Peshawar', 'Quetta', 'Multan', 'Faisalabad',
]

const NGO_CATEGORIES = [
  'Family Law', 'Criminal Law', 'Labour Law', 'Property Law',
  'Inheritance Law', 'Cybercrime', 'Harassment', 'Civil Law / Procedure',
  'Contract Law', 'Consumer Rights', 'Constitutional Law', 'General / Other',
]

const CATEGORY_COLOR = {
  'Family Law':            '#EC4899',
  'Criminal Law':          '#EF4444',
  'Labour Law':            '#F59E0B',
  'Property Law':          '#8B5CF6',
  'Inheritance Law':       '#7C3AED',
  'Cybercrime':            '#06B6D4',
  'Harassment':            '#F97316',
  'Civil Law / Procedure': '#3B82F6',
  'Contract Law':          '#10B981',
  'Consumer Rights':       '#84CC16',
  'Constitutional Law':    '#6366F1',
  'General / Other':       '#64748B',
}
const categoryColor = (cat) => CATEGORY_COLOR[cat] || '#64748B'

export default function NGOPage() {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)

  const [ngos,           setNgos]           = useState([])
  const [loading,        setLoading]        = useState(true)
  const [cityFilter,     setCityFilter]     = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [search,         setSearch]         = useState('')

  useEffect(() => {
    setLoading(true)
    getNGOs({ city: cityFilter, category: categoryFilter })
      .then(r => setNgos(r.ngos || []))
      .catch(() => setNgos([]))
      .finally(() => setLoading(false))
  }, [cityFilter, categoryFilter])

  const filtered = ngos.filter(n =>
    !search ||
    n.ngo_name?.toLowerCase().includes(search.toLowerCase()) ||
    n.category?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <PageContainer size="medium">
      <SectionHeader
        eyebrow={t('ngo_eyebrow')}
        title={t('ngo_title')}
        description={t('ngo_sub')}
      />

      {/* ── Filters ── */}
      <Card padding="p-4" className="mb-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={t('ngo_search_ph')}
              className="input pl-9"
            />
          </div>

          <select value={cityFilter} onChange={e => setCityFilter(e.target.value)} className="input">
            <option value="">{t('ngo_all_cities')}</option>
            {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="input">
            <option value="">{t('ngo_all_areas')}</option>
            {NGO_CATEGORIES.map(c => <option key={c} value={c}>{translateCategory(c, language)}</option>)}
          </select>
        </div>
      </Card>

      {/* ── Result count ── */}
      {!loading && (
        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
          {filtered.length} {filtered.length === 1 ? t('ngo_found_one') : t('ngo_found')}
        </p>
      )}

      {/* ── List ── */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner size={32} />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="🏢"
          title={t('ngo_not_found')}
          description={t('ngo_adjust')}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((ngo, i) => (
            <NGOCard key={ngo.ngo_id || i} ngo={ngo} index={i} />
          ))}
        </div>
      )}
    </PageContainer>
  )
}

function NGOCard({ ngo, index }) {
  const t = useT()
  const { language } = useAppStore()
  const color = categoryColor(ngo.category)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      whileHover={{ scale: 1.015, y: -2 }}
      className="card p-5"
    >
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${color}22` }}
        >
          <Building2 size={18} style={{ color }} />
        </div>

        {/* Content — LTR: NGO names, phones, emails are English data */}
        <div className="flex-1 min-w-0" dir="ltr">
          <h3 className="font-semibold text-sm leading-snug" style={{ color: 'var(--text-primary)' }}>
            {ngo.ngo_name}
          </h3>

          <div className="flex flex-wrap gap-1 mt-1.5">
            {ngo.category && (
              <span
                className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                style={{
                  background:  `${color}22`,
                  color,
                  border: `1px solid ${color}44`,
                }}
              >
                {translateCategory(ngo.category, language)}
              </span>
            )}
            {ngo.city && <Badge variant="neutral">📍 {ngo.city}</Badge>}
            {ngo.active === 0 && <Badge variant="danger">{t('ngo_inactive')}</Badge>}
          </div>

          <div className="flex flex-wrap gap-3 mt-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
            {ngo.contact_phone && (
              <a href={`tel:${ngo.contact_phone}`} className="flex items-center gap-1 hover:underline">
                <Phone size={11} /> {ngo.contact_phone}
              </a>
            )}
            {ngo.contact_email && (
              <a href={`mailto:${ngo.contact_email}`} className="flex items-center gap-1 hover:underline">
                <Mail size={11} /> {ngo.contact_email}
              </a>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

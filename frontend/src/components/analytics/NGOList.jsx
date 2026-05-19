import { motion } from 'framer-motion'
import { Phone, Mail, Globe, Building2, Tag } from 'lucide-react'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { useAppStore } from '@/services/store'

export default function NGOList({ ngos, caseType }) {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)

  if (!ngos?.length) return (
    <p className="text-sm" dir={rtl ? 'rtl' : 'ltr'} style={{ color: 'var(--text-muted)' }}>
      {t('ngo_no_results')}
    </p>
  )

  return (
    <div className="space-y-3">
      {/* "Showing matched organizations for X" header */}
      {caseType && (
        <div
          className="flex items-center gap-1.5 text-xs mb-1"
          dir={rtl ? 'rtl' : 'ltr'}
          style={{ color: 'var(--text-muted)' }}
        >
          <Tag size={11} style={{ flexShrink: 0 }} />
          <span>
            {t('ngo_showing')}{' '}
            <strong style={{ color: 'var(--text-secondary)' }}>
              {translateCategory(caseType, language)}
            </strong>
          </span>
        </div>
      )}

      {ngos.map((ngo, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: rtl ? 6 : -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08 }}
          className="rounded-lg p-3"
          style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}
        >
          {/* NGO name row — always LTR: NGO names are English proper nouns */}
          <div className="flex items-center gap-2 mb-2 flex-wrap" dir="ltr">
            <Building2 size={14} style={{ color: 'var(--success)', flexShrink: 0 }} />
            <span className="font-semibold text-sm" style={{ color: 'var(--success)' }}>
              {ngo.name}
            </span>
            {ngo.category && ngo.category !== caseType && (
              <span
                className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                style={{ background: 'rgba(52,211,153,0.12)', color: 'var(--success)' }}
              >
                {translateCategory(ngo.category, language)}
              </span>
            )}
          </div>

          {/* Metadata row — always LTR: phone numbers, URLs, emails */}
          <div className="flex flex-wrap gap-3 text-xs" dir="ltr" style={{ color: 'var(--text-muted)' }}>
            {ngo.city && <span>📍 {ngo.city}</span>}
            {ngo.phone && (
              <a href={`tel:${ngo.phone}`} className="flex items-center gap-1 hover:underline">
                <Phone size={11} /> {ngo.phone}
              </a>
            )}
            {ngo.email && (
              <a href={`mailto:${ngo.email}`} className="flex items-center gap-1 hover:underline">
                <Mail size={11} /> {ngo.email}
              </a>
            )}
            {ngo.website && (
              <a href={ngo.website} target="_blank" rel="noopener" className="flex items-center gap-1 hover:underline">
                <Globe size={11} /> {t('ngo_website')}
              </a>
            )}
          </div>

          {/* Description — dir="auto" lets browser detect Urdu vs English */}
          {ngo.description && (
            <p className="text-xs mt-2" dir="auto" style={{ color: 'var(--text-secondary)' }}>
              {ngo.description}
            </p>
          )}
        </motion.div>
      ))}
    </div>
  )
}

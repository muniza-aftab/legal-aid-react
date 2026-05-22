import { motion } from 'framer-motion'
import { useT } from '@/services/i18n'

export default function SourcesPanel({ sources, language }) {
  const t = useT()

  if (!sources?.length) return (
    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('no_sources')}</p>
  )

  return (
    <div className="space-y-3">
      {sources.map((src, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05 }}
          className="card p-3"
        >
          {/* Header row: always LTR — law name left, score badge right */}
          <div className="flex items-center justify-between gap-2 mb-1" dir="ltr">
            <span className="font-semibold text-xs" style={{ color: 'var(--primary)' }}>
              📜 {src.law_name}
            </span>
            <span className="badge badge-neutral text-[10px] flex-shrink-0">
              {(src.score * 100).toFixed(0)}% {t('pct_match')}
            </span>
          </div>

          {/* Section code: always LTR (English legal reference) */}
          {src.section && (
            <div className="text-[10px] font-mono mb-1" dir="ltr" style={{ color: 'var(--text-muted)' }}>
              §{src.section}
            </div>
          )}

          {/* Excerpt: English legal text — always LTR and left-aligned */}
          <p className="text-xs leading-relaxed" dir="ltr" style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
            {src.text?.slice(0, 300)}…
          </p>
        </motion.div>
      ))}
    </div>
  )
}

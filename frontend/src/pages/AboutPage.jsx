import { motion } from 'framer-motion'
import { useT } from '@/services/i18n'
import { useAppStore } from '@/services/store'
import { SectionHeader, Card } from '@/components/ui/index'
import { PageContainer } from '@/components/layout/PageLayout'

export default function AboutPage() {
  const t = useT()
  const { language } = useAppStore()

  const features = [
    { icon: '🤖', title: t('feat_ai_title'),   desc: t('feat_ai_desc') },
    { icon: '📚', title: t('feat_rag_title'),   desc: t('feat_rag_desc') },
    { icon: '🌐', title: t('feat_ml_title'),    desc: t('feat_ml_desc') },
    { icon: '🔒', title: t('feat_priv_title'),  desc: t('feat_priv_desc') },
    { icon: '🏢', title: t('feat_ngo_title'),   desc: t('feat_ngo_desc') },
    { icon: '📄', title: t('feat_pdf_title'),   desc: t('feat_pdf_desc') },
  ]

  return (
    <PageContainer size="compact" align="center">
      <SectionHeader
        eyebrow={t('about_eyebrow')}
        title={t('about_title')}
        description={t('about_sub')}
      />

      <div className="space-y-5">
        <Card padding="p-6" className="card-important">
          <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{t('about_what_title')}</h3>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {t('about_what_body')}
          </p>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {features.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              whileHover={{ scale: 1.015, y: -2 }}
              className="card p-4 text-center"
            >
              <div className="text-3xl mb-2">{f.icon}</div>
              <div className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>{f.title}</div>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{f.desc}</p>
            </motion.div>
          ))}
        </div>

        <Card padding="p-6" className="card-important">
          <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{t('about_disclaimer_title')}</h3>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {t('about_disclaimer_body')}
          </p>
        </Card>

        <Card padding="p-6" className="card-important">
          <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{t('about_tech_title')}</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[
              ['Frontend', 'React + Vite + TailwindCSS'],
              ['Backend', 'FastAPI + Python'],
              ['AI/LLM', 'Groq (gpt-oss + Whisper)'],
              ['RAG', 'FAISS + Sentence Transformers'],
              ['Database', 'SQLite'],
              ['TTS', 'ElevenLabs / gTTS'],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="font-mono text-xs font-semibold" style={{ color: '#22D3EE', minWidth: 90 }}>{k}</span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{v}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </PageContainer>
  )
}

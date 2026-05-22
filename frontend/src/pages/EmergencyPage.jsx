import { motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { useT, isRTL } from '@/services/i18n'
import { useAppStore } from '@/services/store'
import { SectionHeader, Card, Alert } from '@/components/ui/index'
import { PageContainer } from '@/components/layout/PageLayout'

const CONTACTS = [
  { label: 'Police',            number: '15',   icon: '🚔', color: '#a78bfa', bg: 'rgba(124,58,237,0.12)', border: 'rgba(124,58,237,0.25)' },
  { label: 'Edhi Foundation',   number: '115',  icon: '🚑', color: '#34d399', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.25)' },
  { label: 'Women Helpline',    number: '1099', icon: '👩', color: '#f9a8d4', bg: 'rgba(236,72,153,0.12)', border: 'rgba(236,72,153,0.25)' },
  { label: 'Cyber Crime (FIA)', number: '9911', icon: '🛡️', color: '#67e8f9', bg: 'rgba(34,211,238,0.12)', border: 'rgba(34,211,238,0.25)' },
  { label: 'Rescue',            number: '1122', icon: '🔥', color: '#fca5a5', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.25)' },
  { label: 'Child Protection',  number: '1121', icon: '👶', color: '#fcd34d', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
]

export default function EmergencyPage() {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)

  const STEPS = [
    { icon: '📱', title: t('estep1_title'), desc: t('estep1_desc') },
    { icon: '📸', title: t('estep2_title'), desc: t('estep2_desc') },
    { icon: '🏥', title: t('estep3_title'), desc: t('estep3_desc') },
    { icon: '📋', title: t('estep4_title'), desc: t('estep4_desc') },
    { icon: '⚖️', title: t('estep5_title'), desc: t('estep5_desc') },
    { icon: '🏢', title: t('estep6_title'), desc: t('estep6_desc') },
  ]

  return (
    <PageContainer size="standard" align="center">
      <SectionHeader
        eyebrow={t('emergency_eyebrow')}
        title={t('emergency_title')}
        description={t('emergency_sub')}
      />

      <Alert type="danger" className="mb-6">
        <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
        <span>{t('emergency_alert')} <strong>15 (Police)</strong> {language === 'Urdu' ? 'یا' : 'or'} <strong>1122 (Rescue)</strong>.</span>
      </Alert>

      {/* Emergency contacts */}
      <div className="label mb-3">{t('emergency_contacts_label')}</div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
        {CONTACTS.map((c, i) => (
          <motion.a
            key={i}
            href={`tel:${c.number}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            whileHover={{ scale: 1.015, y: -2 }}
            className="card p-4 text-center cursor-pointer block transition-all"
            style={{ background: c.bg, borderColor: c.border }}
          >
            <div className="text-3xl mb-2">{c.icon}</div>
            <div className="font-bold text-2xl font-mono mb-1" style={{ color: c.color }}>{c.number}</div>
            <div className="text-xs font-semibold" style={{ color: c.color }}>{c.label}</div>
          </motion.a>
        ))}
      </div>

      {/* Steps */}
      <div className="label mb-3">{t('emergency_steps_label')}</div>
      <div className="space-y-3">
        {STEPS.map((step, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.07 }}
            className="card p-4 flex items-start gap-4"
          >
            <div className="text-2xl flex-shrink-0">{step.icon}</div>
            <div>
              <div className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
                {t('step_prefix')} {i + 1}: {step.title}
              </div>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{step.desc}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Disclaimer */}
      <Card padding="p-4" className="mt-6">
        <p className="text-xs text-center" style={{ color: 'var(--text-muted)' }}>
          {t('emergency_disclaimer')}
        </p>
      </Card>
    </PageContainer>
  )
}

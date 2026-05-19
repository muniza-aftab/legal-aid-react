import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, X } from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT } from '@/services/i18n'

export default function FloatingAIButton() {
  const { aiDrawerOpen, toggleAiDrawer } = useAppStore()
  const t = useT()

  return (
    <AnimatePresence mode="wait">
      {!aiDrawerOpen && (
        <motion.button
          key="fab"
          onClick={toggleAiDrawer}
          initial={{ scale: 0, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0, opacity: 0, y: 20 }}
          transition={{ type: 'spring', stiffness: 300, damping: 26 }}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.94 }}
          className="fixed bottom-6 right-6 z-30 flex items-center gap-2.5 px-5 py-3.5 rounded-2xl text-sm font-semibold text-white select-none"
          style={{
            background:  'linear-gradient(135deg, #7C3AED 0%, #3B82F6 100%)',
            boxShadow:   '0 4px 32px rgba(124,58,237,0.55), 0 0 0 1px rgba(124,58,237,0.35), 0 1px 0 rgba(255,255,255,0.14) inset',
          }}
          aria-label={t('ask_legal_ai')}
        >
          {/* Pulsing glow ring */}
          <span
            className="absolute inset-0 rounded-2xl pointer-events-none"
            style={{
              background: 'transparent',
              boxShadow:  '0 0 0 0 rgba(124,58,237,0.55)',
              animation:  'fab-pulse 2.4s ease-out infinite',
            }}
          />

          <MessageSquare size={17} />
          <span>{t('ask_legal_ai')}</span>
        </motion.button>
      )}
    </AnimatePresence>
  )
}

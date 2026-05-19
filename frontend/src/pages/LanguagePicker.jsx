import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Globe, Building2, AlertTriangle, Lock, CheckCircle, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/services/store'

const FEATURES = [
  {
    icon: Brain,
    en: 'AI Legal Analysis',
    ur: 'اے آئی قانونی تجزیہ',
    enDesc: 'RAG-powered case analysis against Pakistan\'s legal framework',
    urDesc: 'پاکستانی قانونی ڈھانچے کے خلاف کیس کا تجزیہ',
  },
  {
    icon: Globe,
    en: 'Bilingual Support',
    ur: 'دو لسانی حمایت',
    enDesc: 'Full English & Urdu with right-to-left text support',
    urDesc: 'انگریزی اور اردو میں مکمل حمایت',
  },
  {
    icon: Building2,
    en: 'NGO & Lawyer Connect',
    ur: 'این جی او اور وکیل',
    enDesc: 'Get matched with legal aid organizations near you',
    urDesc: 'اپنے قریب قانونی امدادی تنظیموں سے ملیں',
  },
  {
    icon: AlertTriangle,
    en: 'Emergency Helplines',
    ur: 'ہنگامی ہیلپ لائن',
    enDesc: 'Instant access to emergency legal contacts',
    urDesc: 'ہنگامی قانونی رابطوں تک فوری رسائی',
  },
]

export default function LanguagePicker() {
  const setLanguage = useAppStore(s => s.setLanguage)
  const navigate = useNavigate()
  const [selected, setSelected] = useState(null)
  const [entering, setEntering] = useState(false)

  function handleSelect(lang) {
    setSelected(lang)
  }

  function handleEnter() {
    if (!selected || entering) return
    setEntering(true)
    setLanguage(selected)
    setTimeout(() => navigate('/home'), 500)
  }

  const isUrdu = selected === 'Urdu'

  return (
    <div
      className="min-h-screen relative overflow-auto"
      style={{ background: '#0B1120' }}
    >
      {/* Ambient gradient blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute top-0 right-0 w-[700px] h-[700px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(124,58,237,0.18) 0%, transparent 65%)',
            transform: 'translate(25%, -25%)',
          }}
        />
        <div
          className="absolute bottom-0 left-0 w-[600px] h-[600px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(34,211,238,0.12) 0%, transparent 65%)',
            transform: 'translate(-25%, 25%)',
          }}
        />
        <div
          className="absolute top-1/2 left-1/2 w-[900px] h-[900px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 60%)',
            transform: 'translate(-50%, -50%)',
          }}
        />
      </div>

      <AnimatePresence>
        {!entering && (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.35 }}
            className="relative z-10 flex flex-col items-center px-4 py-12 max-w-4xl mx-auto"
          >
            {/* ── Hero ── */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease: 'easeOut' }}
              className="text-center mb-12"
            >
              {/* Emblem */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1, duration: 0.5, type: 'spring', stiffness: 180 }}
                className="inline-flex items-center justify-center w-24 h-24 rounded-2xl mb-6 text-5xl shadow-2xl"
                style={{
                  background: 'linear-gradient(135deg, #7C3AED 0%, #22D3EE 100%)',
                  boxShadow: '0 0 60px rgba(124,58,237,0.50), 0 20px 40px rgba(0,0,0,0.5)',
                }}
              >
                ⚖️
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="font-display text-4xl md:text-5xl font-bold mb-2"
                style={{ letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #a78bfa, #22D3EE)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}
              >
                Pakistan AI Legal Aid
              </motion.h1>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.35 }}
                className="font-urdu text-xl mb-3"
                style={{ color: 'rgba(255,255,255,0.55)', direction: 'rtl' }}
              >
                پاکستان اے آئی قانونی مدد
              </motion.p>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.45 }}
                className="flex flex-wrap justify-center gap-3 mt-4"
              >
                {['RAG-Powered', 'Multilingual', 'Free', 'Private'].map((tag, i) => (
                  <span
                    key={tag}
                    className="text-xs font-semibold px-3 py-1 rounded-full border"
                    style={{
                      color: 'rgba(167,139,250,0.90)',
                      borderColor: 'rgba(124,58,237,0.28)',
                      background: 'rgba(124,58,237,0.09)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </motion.div>
            </motion.div>

            {/* ── Feature Grid ── */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.45 }}
              className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full mb-12"
            >
              {FEATURES.map((f, i) => (
                <motion.div
                  key={f.en}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.55 + i * 0.07 }}
                  className="rounded-xl p-4 text-center border"
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    borderColor: 'rgba(255,255,255,0.08)',
                  }}
                >
                  <div
                    className="inline-flex items-center justify-center w-10 h-10 rounded-lg mb-3"
                    style={{ background: 'rgba(124,58,237,0.18)' }}
                  >
                    <f.icon size={18} style={{ color: '#a78bfa' }} />
                  </div>
                  <div className="text-sm font-semibold text-white mb-1">{f.en}</div>
                  <div className="text-xs font-urdu" style={{ color: 'rgba(255,255,255,0.4)', direction: 'rtl' }}>
                    {f.ur}
                  </div>
                </motion.div>
              ))}
            </motion.div>

            {/* ── Language Selection ── */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.75 }}
              className="w-full max-w-lg"
            >
              <div
                className="rounded-2xl border p-6 md:p-8"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  borderColor: 'rgba(124,58,237,0.22)',
                  backdropFilter: 'blur(8px)',
                }}
              >
                <div className="text-center mb-6">
                  <p className="text-base font-semibold text-white mb-1">
                    Choose your language to continue
                  </p>
                  <p className="text-sm font-urdu" style={{ color: 'rgba(255,255,255,0.45)', direction: 'rtl' }}>
                    جاری رکھنے کے لیے اپنی زبان منتخب کریں
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-5">
                  <LangButton
                    label="English"
                    sub="Continue in English"
                    selected={selected === 'English'}
                    onClick={() => handleSelect('English')}
                  />
                  <LangButton
                    label="اردو"
                    sub="اردو میں جاری رکھیں"
                    selected={selected === 'Urdu'}
                    onClick={() => handleSelect('Urdu')}
                    rtl
                  />
                </div>

                {/* Enter App Button */}
                <AnimatePresence>
                  {selected && (
                    <motion.button
                      key="enter-btn"
                      initial={{ opacity: 0, y: 8, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.25 }}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleEnter}
                      className="w-full flex items-center justify-center gap-2 rounded-xl py-3.5 font-bold text-sm transition-all"
                      style={{
                        background: 'linear-gradient(135deg, #7C3AED 0%, #22D3EE 100%)',
                        color: '#fff',
                        boxShadow: '0 4px 24px rgba(124,58,237,0.50)',
                      }}
                    >
                      <CheckCircle size={16} />
                      {selected === 'Urdu' ? 'ایپ میں داخل ہوں' : 'Enter App'}
                      <ArrowRight size={16} />
                    </motion.button>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>

            {/* ── Trust footer ── */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="mt-8 text-center space-y-2"
            >
              <div className="flex flex-wrap justify-center gap-4 text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>
                <span className="flex items-center gap-1"><Lock size={10} /> No data stored</span>
                <span>·</span>
                <span>100% Free</span>
                <span>·</span>
                <span>Powered by Groq + FAISS</span>
              </div>
              <p className="text-xs" style={{ color: 'rgba(255,255,255,0.18)' }}>
                You can change your language anytime from the sidebar settings.
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading transition overlay */}
      <AnimatePresence>
        {entering && (
          <motion.div
            key="entering"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center"
            style={{ background: '#0B1120' }}
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="text-center"
            >
              <div
                className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl mx-auto mb-5"
                style={{ background: 'linear-gradient(135deg, #7C3AED, #22D3EE)', boxShadow: '0 0 40px rgba(124,58,237,0.5)' }}
              >⚖️</div>
              <p className="text-sm font-semibold" style={{ color: '#a78bfa' }}>
                {selected === 'Urdu' ? 'لوڈ ہو رہا ہے…' : 'Loading your workspace…'}
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function LangButton({ label, sub, selected, onClick, rtl }) {
  return (
    <motion.button
      whileHover={{ scale: 1.03, y: -2 }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className="rounded-xl p-5 border text-center transition-all duration-200 relative overflow-hidden"
      style={{
        background: selected ? 'rgba(124,58,237,0.18)' : 'rgba(255,255,255,0.05)',
        borderColor: selected ? 'rgba(124,58,237,0.65)' : 'rgba(255,255,255,0.09)',
        boxShadow: selected ? '0 0 24px rgba(124,58,237,0.25)' : 'none',
      }}
    >
      {selected && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #7C3AED, #22D3EE)' }}
        >
          <CheckCircle size={12} color="#fff" />
        </motion.div>
      )}
      <div className={`font-bold text-white text-lg mb-1 ${rtl ? 'font-urdu' : ''}`}>{label}</div>
      <div
        className={`text-xs ${rtl ? 'font-urdu' : ''}`}
        style={{ color: 'rgba(255,255,255,0.45)', direction: rtl ? 'rtl' : 'ltr' }}
      >
        {sub}
      </div>
    </motion.button>
  )
}

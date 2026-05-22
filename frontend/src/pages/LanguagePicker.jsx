import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, CheckCircle, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/services/store'


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
              className="text-center mb-10"
            >
              {/* Emblem */}
              <motion.div
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1, duration: 0.5, type: 'spring', stiffness: 180 }}
                className="inline-flex items-center justify-center w-24 h-24 rounded-2xl mb-4 text-5xl shadow-2xl"
                style={{
                  background: 'linear-gradient(135deg, #7C3AED 0%, #22D3EE 100%)',
                  boxShadow: '0 0 48px rgba(124,58,237,0.40), 0 20px 40px rgba(0,0,0,0.5)',
                }}
              >
                ⚖️
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="font-display text-3xl md:text-4xl font-bold mb-2"
                style={{ letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #a78bfa, #22D3EE)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}
              >
                Pakistan AI Legal Aid
              </motion.h1>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.35 }}
                className="font-urdu text-xl mb-3"
                style={{ color: 'rgba(255,255,255,0.68)', direction: 'rtl' }}
              >
                پاکستان اے آئی قانونی مدد
              </motion.p>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.45 }}
                className="flex flex-wrap justify-center gap-3 mt-4"
              >
                {['RAG-Powered', 'Bilingual', 'Private'].map((tag, i) => (
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

            {/* ── Language Selection ── */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.75 }}
              className="w-full max-w-sm"
            >
              <div className="text-center mb-5">
                  <p className="text-lg font-semibold text-white mb-1">
                    Choose your language.
                  </p>
                  <p className="text-sm font-urdu" style={{ color: 'rgba(255,255,255,0.45)', direction: 'rtl' }}>
                    جاری رکھنے کے لیے اپنی زبان منتخب کریں
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-5">
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
                      className="w-full flex items-center justify-center gap-2 rounded-xl py-3.5 font-bold text-sm transition-all mb-4"
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

                <div className="mt-5">
                  <div className="mb-3" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />
                  <div className="text-center space-y-2.5">
                    <div className="flex flex-wrap justify-center items-center gap-3 text-xs" style={{ color: 'rgba(255,255,255,0.33)' }}>
                      <span className="flex items-center gap-1"><Lock size={10} />No data stored</span>
                      <span>·</span>
                      <span>100% Free</span>
                      <span>·</span>
                      <span>Powered by Groq + FAISS</span>
                    </div>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.24)' }}>
                      You can change your language anytime from the sidebar settings.
                    </p>
                  </div>
                </div>
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
      whileHover={{
        scale: 1.02,
        y: -3,
        boxShadow: selected
          ? '0 8px 28px rgba(124,58,237,0.40)'
          : '0 6px 20px rgba(124,58,237,0.18)',
      }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 320, damping: 22 }}
      onClick={onClick}
      className="rounded-xl px-6 py-10 border text-center relative overflow-hidden"
      style={{
        background: selected ? 'rgba(124,58,237,0.18)' : 'rgba(255,255,255,0.05)',
        borderColor: selected ? 'rgba(124,58,237,0.65)' : 'rgba(255,255,255,0.11)',
        boxShadow: selected ? '0 0 26px rgba(124,58,237,0.28)' : 'none',
        transition: 'background 0.2s, border-color 0.2s, box-shadow 0.2s',
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
      <div className={`font-bold text-white text-xl mb-1 ${rtl ? 'font-urdu' : ''}`}>{label}</div>
      <div
        className={`text-xs ${rtl ? 'font-urdu' : ''}`}
        style={{ color: 'rgba(255,255,255,0.50)', direction: rtl ? 'rtl' : 'ltr' }}
      >
        {sub}
      </div>
    </motion.button>
  )
}

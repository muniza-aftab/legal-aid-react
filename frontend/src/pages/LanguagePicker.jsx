import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, CheckCircle } from 'lucide-react'
import { useAppStore } from '@/services/store'

/* ─── Background: flowing blue waves bottom-left ─── */
function WavesBottomLeft() {
  const waves = [
    { d: 'M -10 580 C 80 450 230 260 520 110', sw: 1.6, op: 1.00 },
    { d: 'M -10 530 C 100 400 270 200 560  60', sw: 1.3, op: 0.82 },
    { d: 'M -10 480 C 120 350 310 140 600  10', sw: 1.0, op: 0.64 },
    { d: 'M -10 430 C 140 300 350  80 640 -40', sw: 0.8, op: 0.45 },
    { d: 'M -10 380 C 160 250 390  20 680 -90', sw: 0.6, op: 0.26 },
  ]
  return (
    <svg
      className="absolute bottom-0 left-0"
      width="700" height="600"
      viewBox="0 0 700 600"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <filter id="glBL" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <linearGradient id="grBL" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#1D4ED8" stopOpacity="1" />
          <stop offset="52%"  stopColor="#3B82F6" stopOpacity="0.65" />
          <stop offset="100%" stopColor="#93C5FD" stopOpacity="0" />
        </linearGradient>
      </defs>
      {waves.map((w, i) => (
        <path
          key={i}
          d={w.d}
          stroke="url(#grBL)"
          strokeWidth={w.sw}
          fill="none"
          opacity={w.op}
          filter={i < 3 ? 'url(#glBL)' : undefined}
        />
      ))}
    </svg>
  )
}

/* ─── Background: flowing purple waves top-right ─── */
function WavesTopRight() {
  const waves = [
    { d: 'M 710 -10 C 620 110 460 300 160 450', sw: 1.5, op: 1.00 },
    { d: 'M 710  40 C 600 165 425 360 110 510', sw: 1.2, op: 0.80 },
    { d: 'M 710  90 C 580 220 390 420  60 572', sw: 0.95, op: 0.62 },
    { d: 'M 710 140 C 560 275 355 480  10 634', sw: 0.75, op: 0.43 },
    { d: 'M 710 190 C 540 330 320 540 -40 696', sw: 0.6,  op: 0.25 },
  ]
  return (
    <svg
      className="absolute top-0 right-0"
      width="720" height="580"
      viewBox="0 0 720 580"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <filter id="glTR" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <linearGradient id="grTR" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#7C3AED" stopOpacity="1" />
          <stop offset="52%"  stopColor="#8B5CF6" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#C4B5FD" stopOpacity="0" />
        </linearGradient>
      </defs>
      {waves.map((w, i) => (
        <path
          key={i}
          d={w.d}
          stroke="url(#grTR)"
          strokeWidth={w.sw}
          fill="none"
          opacity={w.op}
          filter={i < 3 ? 'url(#glTR)' : undefined}
        />
      ))}
    </svg>
  )
}

/* ─── Background: Islamic geometric pattern overlay ─── */
function IslamicPattern({ id, corner }) {
  const isTR = corner === 'tr'
  return (
    <svg
      className={`absolute ${isTR ? 'top-0 right-0' : 'bottom-0 left-0'}`}
      width="300" height="300"
      viewBox="0 0 300 300"
      fill="none"
      aria-hidden="true"
      style={{ opacity: 0.065 }}
    >
      <defs>
        {/* 8-pointed star tile, 56×56 */}
        <pattern id={`ip${id}`} x="0" y="0" width="56" height="56" patternUnits="userSpaceOnUse">
          {/* 8-pointed star polygon */}
          <polygon
            points="28,4 33,19 48,19 36.5,28.5 41,44 28,35 15,44 19.5,28.5 8,19 23,19"
            stroke="white" strokeWidth="0.7" fill="none"
          />
          {/* Outer rotated square frame */}
          <rect x="14" y="14" width="28" height="28"
            transform="rotate(45 28 28)" stroke="white" strokeWidth="0.4" fill="none" />
          {/* Corner cross-diamonds (tile edges) */}
          <rect x="-10" y="-10" width="20" height="20"
            transform="rotate(45 0 0)" stroke="white" strokeWidth="0.35" fill="none" />
          <rect x="46" y="-10" width="20" height="20"
            transform="rotate(45 56 0)" stroke="white" strokeWidth="0.35" fill="none" />
          <rect x="46" y="46" width="20" height="20"
            transform="rotate(45 56 56)" stroke="white" strokeWidth="0.35" fill="none" />
          <rect x="-10" y="46" width="20" height="20"
            transform="rotate(45 0 56)" stroke="white" strokeWidth="0.35" fill="none" />
        </pattern>
        {/* Radial fade mask — strong at corner, gone toward center */}
        <radialGradient id={`pm${id}`}
          cx={isTR ? '100%' : '0%'} cy={isTR ? '0%' : '100%'} r="90%">
          <stop offset="0%"   stopColor="white" stopOpacity="1" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id={`mm${id}`}>
          <rect width="300" height="300" fill={`url(#pm${id})`} />
        </mask>
      </defs>
      <rect width="300" height="300" fill={`url(#ip${id})`} mask={`url(#mm${id})`} />
    </svg>
  )
}

/* ─── Background: sparse star particles ─── */
function StarParticles() {
  /* Coordinates in a 0–100 viewBox space, clustered near edges */
  const pts = [
    [8,  12, 0.18, 0.50], [15,  6, 0.13, 0.36], [22, 19, 0.13, 0.28],
    [75,  8, 0.18, 0.48], [88, 15, 0.13, 0.38], [92,  5, 0.13, 0.30],
    [5,  36, 0.13, 0.26], [10, 56, 0.18, 0.36], [ 3, 73, 0.13, 0.28],
    [95, 41, 0.13, 0.30], [90, 63, 0.18, 0.22], [97, 25, 0.10, 0.20],
    [20, 88, 0.13, 0.28], [35, 93, 0.18, 0.36], [65, 91, 0.13, 0.26],
    [80, 86, 0.13, 0.30], [50,  4, 0.15, 0.24], [49, 95, 0.15, 0.20],
    [12, 28, 0.10, 0.22], [86, 78, 0.10, 0.20], [27, 44, 0.09, 0.16],
    [71, 38, 0.09, 0.16], [30, 72, 0.09, 0.14], [67, 74, 0.09, 0.14],
    [42,  9, 0.10, 0.18], [58,  7, 0.10, 0.18], [18, 82, 0.10, 0.16],
    [78, 20, 0.12, 0.22], [ 6, 48, 0.10, 0.18], [93, 52, 0.10, 0.16],
  ]
  return (
    <svg
      className="absolute inset-0 w-full h-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      {pts.map(([cx, cy, r, op], i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill="white" opacity={op} />
      ))}
    </svg>
  )
}

/* ─── Page ─── */
export default function LanguagePicker() {
  const setLanguage = useAppStore(s => s.setLanguage)
  const navigate = useNavigate()
  const [selected, setSelected] = useState(null)
  const [entering, setEntering] = useState(false)

  function handleSelect(lang) {
    if (entering) return
    setSelected(lang)
    setTimeout(() => {
      setLanguage(lang)
      setEntering(true)
      setTimeout(() => navigate('/home'), 500)
    }, 300)
  }

  return (
    <div
      className="min-h-screen relative overflow-auto"
      style={{ background: '#050914' }}
    >
      {/* ══ Premium background system ══ */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none select-none">

        {/* Base vertical gradient — adds subtle depth top→bottom */}
        <div className="absolute inset-0" style={{
          background: 'linear-gradient(175deg, #060B1D 0%, #040812 50%, #070C1F 100%)',
        }} />

        {/* Ambient bloom — blue, bottom-left */}
        <div className="absolute bottom-0 left-0" style={{
          width: '680px', height: '560px',
          background: 'radial-gradient(ellipse at 20% 80%, rgba(29,78,216,0.44) 0%, rgba(37,99,235,0.18) 38%, transparent 66%)',
          transform: 'translate(-8%, 8%)',
        }} />

        {/* Ambient bloom — purple, top-right */}
        <div className="absolute top-0 right-0" style={{
          width: '620px', height: '540px',
          background: 'radial-gradient(ellipse at 80% 20%, rgba(109,40,217,0.38) 0%, rgba(124,58,237,0.15) 40%, transparent 66%)',
          transform: 'translate(8%, -8%)',
        }} />

        {/* Corner wave systems */}
        <WavesBottomLeft />
        <WavesTopRight />

        {/* Islamic geometric patterns */}
        <IslamicPattern id="tr" corner="tr" />
        <IslamicPattern id="bl" corner="bl" />

        {/* Sparse star particles */}
        <StarParticles />

        {/* Center readability vignette — keeps content area clean */}
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse 55% 60% at 50% 50%, rgba(4,8,18,0.52) 0%, transparent 100%)',
        }} />
      </div>

      {/* ══ Content ══ */}
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
                className="inline-flex items-center justify-center w-24 h-24 rounded-2xl mb-4 text-5xl relative"
                style={{
                  background: 'linear-gradient(135deg, #1E3A8A 0%, #4C1D95 100%)',
                  boxShadow: '0 0 0 1px rgba(139,92,246,0.30), 0 0 40px rgba(99,102,241,0.38), 0 0 80px rgba(30,58,138,0.22), 0 18px 36px rgba(0,0,0,0.65)',
                }}
              >
                {/* Glass gloss highlight */}
                <div
                  className="absolute inset-0 rounded-2xl pointer-events-none"
                  style={{
                    background: 'linear-gradient(145deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 45%, transparent 100%)',
                  }}
                />
                {/* Bottom edge shine */}
                <div
                  className="absolute bottom-0 left-1/2 pointer-events-none"
                  style={{
                    width: '60%', height: '1px',
                    background: 'linear-gradient(to right, transparent, rgba(139,92,246,0.50), transparent)',
                    transform: 'translateX(-50%)',
                  }}
                />
                ⚖️
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="font-display text-3xl md:text-4xl font-bold mb-2"
                style={{ letterSpacing: '-0.5px' }}
              >
                <span style={{ color: '#FFFFFF' }}>Pakistan </span>
                <span
                  style={{
                    background: 'linear-gradient(135deg, #8B5CF6 0%, #60A5FA 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  AI Legal Aid
                </span>
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
                {['RAG-Powered', 'Bilingual', 'Private'].map((tag) => (
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

              <div className="mt-5">
                <div className="mb-3" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />
                <div className="text-center space-y-2.5">
                  <div
                    className="flex flex-wrap justify-center items-center gap-3 text-xs"
                    style={{ color: 'rgba(255,255,255,0.33)' }}
                  >
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

      {/* ══ Loading transition overlay ══ */}
      <AnimatePresence>
        {entering && (
          <motion.div
            key="entering"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center"
            style={{ background: '#050914' }}
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="text-center"
            >
              <div
                className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl mx-auto mb-5"
                style={{
                  background: 'linear-gradient(135deg, #7C3AED, #22D3EE)',
                  boxShadow: '0 0 40px rgba(124,58,237,0.5)',
                }}
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

/* ─── Language card button ─── */
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

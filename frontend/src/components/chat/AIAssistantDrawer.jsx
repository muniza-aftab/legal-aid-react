import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Send, Trash2, Volume2, VolumeX, Sparkles } from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { sendChatMessage, clearChatSession, generateTTS } from '@/services/api'
import { Spinner } from '@/components/ui/index'
import ScalesIcon from '@/components/ui/ScalesIcon'

let _ctr = 0
const uid = () => `msg-${Date.now()}-${_ctr++}`
const sid = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

function tok(isDark) {
  return {
    backdropBg:         isDark ? 'rgba(0,0,0,0.18)'   : 'rgba(0,0,0,0.10)',
    panelBg:            isDark ? '#0a1020'             : '#ffffff',
    panelBorderColor:   isDark ? 'rgba(124,58,237,0.30)' : 'rgba(124,58,237,0.20)',
    panelShadow: (rtl) => isDark
      ? (rtl ? '28px 0 80px rgba(0,0,0,0.80),  4px 0 0 0 rgba(124,58,237,0.18)'  : '-28px 0 80px rgba(0,0,0,0.80), -4px 0 0 0 rgba(124,58,237,0.18)')
      : (rtl ? '16px 0 48px rgba(0,0,0,0.14),  2px 0 0 0 rgba(124,58,237,0.12)'  : '-16px 0 48px rgba(0,0,0,0.14), -2px 0 0 0 rgba(124,58,237,0.12)'),
    headerBorderColor:  isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
    titleColor:         isDark ? '#F1F5F9'             : '#0F172A',
    ctxColor:           isDark ? 'rgba(167,139,250,0.80)' : '#6D28D9',
    subtitleColor:      isDark ? 'rgba(255,255,255,0.30)' : 'rgba(15,23,42,0.42)',
    iconColor:          isDark ? 'rgba(241,245,249,0.42)' : 'rgba(15,23,42,0.48)',
    clearHoverBg:       isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)',
    clearHoverColor:    isDark ? 'rgba(241,245,249,0.80)' : '#0F172A',
    closeHoverBg:       isDark ? 'rgba(239,68,68,0.12)'   : 'rgba(220,38,38,0.08)',
    closeHoverColor:    isDark ? '#f87171'                 : '#DC2626',
    disclaimerBg:       isDark ? 'rgba(234,179,8,0.07)'   : '#FFFBEB',
    disclaimerBorder:   isDark ? 'rgba(234,179,8,0.15)'   : 'rgba(146,64,14,0.20)',
    disclaimerColor:    isDark ? '#fcd34d'                 : '#92400E',
    messagesBg:         isDark ? 'transparent'             : '#F8FAFC',
    userBg:             isDark
      ? 'linear-gradient(135deg, rgba(124,58,237,0.42), rgba(59,130,246,0.42))'
      : 'linear-gradient(135deg, #7C3AED, #3B82F6)',
    userColor:          '#FFFFFF',
    userBorder:         isDark ? 'rgba(124,58,237,0.38)'  : 'rgba(124,58,237,0.55)',
    aiBg:               isDark ? 'rgba(255,255,255,0.07)'  : '#F1F5F9',
    aiColor:            isDark ? 'rgba(241,245,249,0.75)'  : '#1E293B',
    aiBorder:           isDark ? 'rgba(255,255,255,0.09)'  : 'rgba(0,0,0,0.09)',
    typingBg:           isDark ? 'rgba(255,255,255,0.07)'  : '#F1F5F9',
    typingBorder:       isDark ? 'rgba(255,255,255,0.09)'  : 'rgba(0,0,0,0.09)',
    typingDot:          isDark ? 'rgba(167,139,250,0.70)'  : 'rgba(109,40,217,0.65)',
    listenBg:           isDark ? 'rgba(255,255,255,0.05)'  : 'rgba(0,0,0,0.04)',
    listenBorder:       isDark ? 'rgba(255,255,255,0.09)'  : 'rgba(0,0,0,0.10)',
    listenColor:        isDark ? 'rgba(241,245,249,0.42)'  : 'rgba(15,23,42,0.48)',
    listenHoverBg:      isDark ? 'rgba(124,58,237,0.14)'   : 'rgba(124,58,237,0.10)',
    listenHoverColor:   isDark ? '#a78bfa'                 : '#6D28D9',
    listenHoverBorder:  isDark ? 'rgba(124,58,237,0.28)'   : 'rgba(124,58,237,0.28)',
    inputAreaBg:        isDark ? 'rgba(255,255,255,0.02)'  : '#F8FAFC',
    inputAreaBorder:    isDark ? 'rgba(255,255,255,0.08)'  : 'rgba(0,0,0,0.08)',
    hintColor:          isDark ? 'rgba(255,255,255,0.22)'  : 'rgba(15,23,42,0.36)',
    kbdBg:              isDark ? 'rgba(255,255,255,0.07)'  : 'rgba(0,0,0,0.06)',
    kbdColor:           isDark ? 'rgba(255,255,255,0.55)'  : 'rgba(15,23,42,0.55)',
    emptyIconBg:        isDark
      ? 'linear-gradient(135deg, rgba(124,58,237,0.18), rgba(34,211,238,0.12))'
      : 'linear-gradient(135deg, rgba(124,58,237,0.10), rgba(59,130,246,0.08))',
    emptyIconBorder:    isDark ? 'rgba(124,58,237,0.28)'   : 'rgba(124,58,237,0.22)',
    emptyIconShadow:    isDark ? '0 8px 32px rgba(124,58,237,0.18)' : '0 4px 20px rgba(124,58,237,0.10)',
    emptyTitleColor:    isDark ? '#F1F5F9'                 : '#0F172A',
    emptySubColor:      isDark ? 'rgba(241,245,249,0.42)'  : 'rgba(15,23,42,0.48)',
    promptBg:           isDark ? 'rgba(255,255,255,0.05)'  : 'rgba(0,0,0,0.04)',
    promptBorder:       isDark ? 'rgba(255,255,255,0.09)'  : 'rgba(0,0,0,0.08)',
    promptColor:        isDark ? 'rgba(241,245,249,0.58)'  : 'rgba(15,23,42,0.60)',
  }
}

export default function AIAssistantDrawer() {
  const {
    language, theme, analysisResult, aiDrawerOpen, closeAiDrawer,
    chatSessionId, chatMessages, setChatSessionId, addChatMessage, clearChat,
  } = useAppStore()

  const t      = useT()
  const rtl    = isRTL(language)
  const isDark = theme === 'dark'
  const tk     = tok(isDark)

  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef   = useRef()
  const textareaRef = useRef()

  useEffect(() => { if (!chatSessionId) setChatSessionId(sid()) }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, loading])

  const resizeTextarea = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  useEffect(() => {
    if (aiDrawerOpen) setTimeout(() => textareaRef.current?.focus(), 280)
  }, [aiDrawerOpen])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeAiDrawer() }
    if (aiDrawerOpen) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [aiDrawerOpen])

  const sendMessage = async (msg) => {
    if (!msg.trim() || loading) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    addChatMessage({ role: 'user', content: msg, id: uid() })
    setLoading(true)
    try {
      const ctx = analysisResult ? {
        category:   analysisResult.category   || '',
        risk_level: analysisResult.risk_level || '',
        summary:    analysisResult.summary    || '',
        last_query: '',
      } : {}
      const resp = await sendChatMessage(chatSessionId || sid(), msg, language, ctx)
      addChatMessage({
        role: 'assistant', content: resp.reply,
        confidence: resp.confidence, sources: resp.sources || [], id: uid(),
      })
    } catch {
      addChatMessage({ role: 'assistant', content: t('chat_error'), id: uid() })
    }
    setLoading(false)
  }

  const handleSend = () => sendMessage(input.trim())

  const handleClear = async () => {
    if (chatSessionId) { try { await clearChatSession(chatSessionId) } catch {} }
    clearChat()
    setChatSessionId(sid())
  }

  const side     = rtl ? 'left' : 'right'
  const slideOut = rtl ? '-100%' : '100%'

  return (
    <AnimatePresence>
      {aiDrawerOpen && (
        <>
          {/* ── Backdrop ── */}
          <motion.div
            key="ai-backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="fixed inset-0 z-[45]"
            style={{ background: tk.backdropBg }}
            onClick={closeAiDrawer}
          />

          {/* ── Drawer Panel ── always LTR for layout; RTL applied per element */}
          <motion.div
            key="ai-drawer"
            initial={{ x: slideOut }} animate={{ x: 0 }} exit={{ x: slideOut }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className={`fixed inset-y-0 ${side}-0 z-50 flex flex-col w-full md:w-[420px]`}
            dir="ltr"
            style={{
              background:   tk.panelBg,
              borderLeft:   rtl ? 'none' : `1px solid ${tk.panelBorderColor}`,
              borderRight:  rtl ? `1px solid ${tk.panelBorderColor}` : 'none',
              boxShadow:    tk.panelShadow(rtl),
            }}
          >

            {/* ── Header ── */}
            <div
              className={`flex items-center justify-between px-5 py-4 flex-shrink-0 border-b ${rtl ? 'flex-row-reverse' : ''}`}
              style={{ borderColor: tk.headerBorderColor }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background: 'rgba(124,58,237,0.10)',
                    border: '1px solid rgba(124,58,237,0.18)',
                  }}
                >
                  <Sparkles size={15} style={{ color: 'rgba(167,139,250,0.72)' }} />
                </div>
                <div className="min-w-0" dir={rtl ? 'rtl' : 'ltr'}>
                  <p className="text-sm font-semibold truncate" style={{ color: tk.titleColor }}>
                    {t('chat_title')}
                  </p>
                  {analysisResult?.category ? (
                    <p className="text-[10px] mt-0.5 truncate" style={{ color: tk.ctxColor }}>
                      {t('context_label')} {translateCategory(analysisResult.category, language)}
                    </p>
                  ) : (
                    <p className="text-[10px] mt-0.5" style={{ color: tk.subtitleColor }}>
                      {t('rag_powered')}
                    </p>
                  )}
                </div>
              </div>

              <div className={`flex items-center gap-1 flex-shrink-0 ${rtl ? 'mr-2' : 'ml-2'}`}>
                <button
                  onClick={handleClear}
                  title={t('chat_clear')}
                  className="flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-lg transition-all"
                  style={{ color: tk.iconColor }}
                  onMouseEnter={e => { e.currentTarget.style.background = tk.clearHoverBg; e.currentTarget.style.color = tk.clearHoverColor }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = tk.iconColor }}
                >
                  <Trash2 size={12} />
                  <span className="hidden sm:inline">{t('chat_clear')}</span>
                </button>
                <button
                  onClick={closeAiDrawer}
                  className="p-1.5 rounded-lg transition-all"
                  style={{ color: tk.iconColor }}
                  onMouseEnter={e => { e.currentTarget.style.background = tk.closeHoverBg; e.currentTarget.style.color = tk.closeHoverColor }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = tk.iconColor }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* ── Disclaimer ── */}
            <div
              className="px-5 py-2 text-[11px] flex-shrink-0 leading-snug"
              dir={rtl ? 'rtl' : 'ltr'}
              style={{
                background:   tk.disclaimerBg,
                borderBottom: `1px solid ${tk.disclaimerBorder}`,
                color:        tk.disclaimerColor,
              }}
            >
              {t('chat_disclaimer')}
            </div>

            {/* ── Messages ── */}
            <div
              className="flex-1 overflow-y-auto px-4 py-5 space-y-5 min-h-0"
              style={{ background: tk.messagesBg }}
            >
              {chatMessages.length === 0 ? (
                <EmptyState t={t} tk={tk} rtl={rtl} onSelectPrompt={sendMessage} />
              ) : (
                chatMessages.map(msg => (
                  <ChatBubble key={msg.id} msg={msg} rtl={rtl} language={language} tk={tk} t={t} />
                ))
              )}
              {loading && <TypingIndicator tk={tk} />}
              <div ref={bottomRef} />
            </div>

            {/* ── Input ── */}
            <div
              className="px-4 py-4 flex-shrink-0"
              style={{
                borderTop:  `1px solid ${tk.inputAreaBorder}`,
                background: tk.inputAreaBg,
              }}
            >
              <div className="flex items-end gap-2">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => { setInput(e.target.value); resizeTextarea() }}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder={t('chat_placeholder')}
                  dir={rtl ? 'rtl' : 'ltr'}
                  rows={1}
                  className="input flex-1 text-sm resize-none leading-relaxed"
                  style={{ minHeight: 42, maxHeight: 120, paddingTop: 10, paddingBottom: 10 }}
                />
                <motion.button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  whileTap={{ scale: 0.92 }}
                  className="btn-primary px-3 flex-shrink-0"
                  style={{ height: 42 }}
                >
                  {loading ? <Spinner size={15} /> : <Send size={15} />}
                </motion.button>
              </div>
              <p className="text-[10px] mt-2 text-center" style={{ color: tk.hintColor }}>
                <kbd className="rounded px-1 py-0.5" style={{ background: tk.kbdBg, color: tk.kbdColor, fontFamily: 'inherit' }}>Enter</kbd>
                {' '}{t('kbd_send')} ·{' '}
                <kbd className="rounded px-1 py-0.5" style={{ background: tk.kbdBg, color: tk.kbdColor, fontFamily: 'inherit' }}>Shift+Enter</kbd>
                {' '}{t('kbd_newline')}
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

/* ── Empty state ── */
function EmptyState({ t, tk, rtl, onSelectPrompt }) {
  const prompts = [t('chat_prompt1'), t('chat_prompt2'), t('chat_prompt3')]
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4 py-8">
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.1, type: 'spring', stiffness: 260, damping: 22 }}
        className="mb-5"
      >
        <svg viewBox="0 0 72 72" width={60} height={60} fill="none" style={{ color: 'rgba(139,92,246,0.38)' }}>
          {/* Chat bubble body */}
          <rect x="4" y="6" width="54" height="42" rx="12"
                stroke="currentColor" strokeWidth="1.6" fill="rgba(124,58,237,0.06)" />
          {/* Bubble tail */}
          <path d="M14 48 L8 62 L30 48"
                stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"
                fill="rgba(124,58,237,0.06)" />
          {/* Text placeholder lines */}
          <line x1="14" y1="21" x2="48" y2="21"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.70" />
          <line x1="14" y1="30" x2="42" y2="30"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.48" />
          <line x1="14" y1="39" x2="36" y2="39"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.30" />
          {/* AI sparkle cluster (top-right) */}
          <circle cx="62" cy="12" r="2.4" fill="currentColor" opacity="0.50" />
          <circle cx="68" cy="22" r="1.6" fill="currentColor" opacity="0.30" />
          <circle cx="65" cy="33" r="1.1" fill="currentColor" opacity="0.18" />
        </svg>
      </motion.div>

      <p className="text-sm font-semibold mb-1.5" style={{ color: tk.emptyTitleColor }}>
        {t('chat_hint')}
      </p>
      <p className="text-xs mb-6" dir={rtl ? 'rtl' : 'ltr'} style={{ color: tk.emptySubColor }}>
        {t('chat_sub')}
      </p>

      <div className="w-full space-y-2">
        {prompts.map((prompt, i) => (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.07 }}
            whileHover={{ scale: 1.015, x: rtl ? -2 : 2 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onSelectPrompt(prompt)}
            className="w-full text-xs px-3 py-2.5 rounded-xl text-left transition-all"
            dir={rtl ? 'rtl' : 'ltr'}
            style={{
              textAlign:  rtl ? 'right' : 'left',
              background: tk.promptBg,
              border:     `1px solid ${tk.promptBorder}`,
              color:      tk.promptColor,
              cursor:     'pointer',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background    = tk.listenHoverBg
              e.currentTarget.style.borderColor   = tk.listenHoverBorder
              e.currentTarget.style.color         = tk.listenHoverColor
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background    = tk.promptBg
              e.currentTarget.style.borderColor   = tk.promptBorder
              e.currentTarget.style.color         = tk.promptColor
            }}
          >
            💬 {prompt}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

/* ── Typing indicator ── */
function TypingIndicator({ tk }) {
  return (
    <div className="flex items-start gap-3">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
        style={{
          background: 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
          boxShadow: '0 0 0 1px rgba(124,58,237,0.40), 0 0 10px rgba(124,58,237,0.45)',
        }}
      >
        <ScalesIcon size={17} gid="adt" />
      </div>
      <div
        className="rounded-2xl rounded-tl-sm px-4 py-3.5 flex items-center gap-1.5"
        style={{ background: tk.typingBg, border: `1px solid ${tk.typingBorder}` }}
      >
        {[0, 0.18, 0.36].map((delay, i) => (
          <motion.span
            key={i}
            className="block w-1.5 h-1.5 rounded-full"
            style={{ background: tk.typingDot }}
            animate={{ y: [0, -4, 0], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 0.9, delay, repeat: Infinity, ease: 'easeInOut' }}
          />
        ))}
      </div>
    </div>
  )
}

/* ── Chat bubble ──
   Row is always dir="ltr" so user/assistant positions never flip in RTL.
   Text inside each bubble gets its own direction based on language.
── */
function ChatBubble({ msg, rtl, language, tk, t }) {
  const isUser = msg.role === 'user'
  const [ttsState, setTtsState] = useState('idle')
  const audioRef = useRef(null)

  const confLabel = {
    high:   t('conf_high'),
    medium: t('conf_medium'),
    low:    t('conf_low'),
  }

  useEffect(() => {
    return () => { if (audioRef.current) { audioRef.current.pause(); audioRef.current = null } }
  }, [])

  const handleListen = async () => {
    if (ttsState === 'playing') {
      audioRef.current?.pause(); return
    }
    if (ttsState === 'paused') {
      audioRef.current?.play(); return
    }
    if (ttsState === 'loading') return
    setTtsState('loading')
    try {
      const blob  = await generateTTS(msg.content, language)
      const url   = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onplay  = () => setTtsState('playing')
      audio.onpause = () => { if (!audio.ended) setTtsState('paused') }
      audio.onended = () => { URL.revokeObjectURL(url); audioRef.current = null; setTtsState('idle') }
      audio.onerror = () => { URL.revokeObjectURL(url); audioRef.current = null; setTtsState('idle') }
      audio.play()
    } catch { setTtsState('idle') }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.20, ease: 'easeOut' }}
      dir="ltr"
      className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      {/* Avatar */}
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs flex-shrink-0 mt-0.5"
        style={{
          background: isUser
            ? 'linear-gradient(135deg, #7C3AED, #3B82F6)'
            : 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
          boxShadow: isUser ? 'none' : '0 0 0 1px rgba(124,58,237,0.40), 0 0 10px rgba(124,58,237,0.40)',
        }}
      >
        {isUser ? '👤' : <ScalesIcon size={17} gid="ada" />}
      </div>

      {/* Content */}
      <div className={`max-w-[84%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
          style={{
            background: isUser ? tk.userBg    : tk.aiBg,
            color:      isUser ? tk.userColor : tk.aiColor,
            border:     `1px solid ${isUser ? tk.userBorder : tk.aiBorder}`,
            direction:  rtl ? 'rtl' : 'ltr',
            textAlign:  rtl ? 'right' : 'left',
            wordBreak:  'break-word',
          }}
        >
          {msg.content}
        </div>

        {/* Footer: confidence + sources + listen (assistant only) */}
        {!isUser && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            {msg.confidence && (
              <span className="badge badge-neutral text-[10px]">
                {msg.confidence === 'high' ? '🟢' : msg.confidence === 'medium' ? '🟡' : '🔴'}{' '}
                {confLabel[msg.confidence] || msg.confidence}
              </span>
            )}
            {msg.sources?.slice(0, 2).map((s, i) => (
              <span
                key={i}
                className="badge badge-primary text-[10px]"
                title={`${(s.score * 100).toFixed(0)}% match`}
              >
                📜 {s.title?.slice(0, 20)}
              </span>
            ))}

            {/* Listen / Stop */}
            <motion.button
              onClick={handleListen}
              disabled={ttsState === 'loading'}
              whileTap={{ scale: 0.92 }}
              className="flex items-center gap-1 text-[10px] font-medium rounded-lg px-2 py-1 transition-all"
              style={{
                color:      ttsState === 'playing' ? '#DC2626' : tk.listenColor,
                background: ttsState === 'playing' ? 'rgba(220,38,38,0.10)' : tk.listenBg,
                border:     `1px solid ${ttsState === 'playing' ? 'rgba(220,38,38,0.28)' : tk.listenBorder}`,
              }}
              onMouseEnter={e => {
                if (ttsState === 'idle' || ttsState === 'paused') {
                  e.currentTarget.style.background   = tk.listenHoverBg
                  e.currentTarget.style.color        = tk.listenHoverColor
                  e.currentTarget.style.borderColor  = tk.listenHoverBorder
                }
              }}
              onMouseLeave={e => {
                if (ttsState === 'idle' || ttsState === 'paused') {
                  e.currentTarget.style.background  = tk.listenBg
                  e.currentTarget.style.color       = tk.listenColor
                  e.currentTarget.style.borderColor = tk.listenBorder
                }
              }}
            >
              {ttsState === 'loading' ? (
                <><Spinner size={10} /> {t('loading_tts')}</>
              ) : ttsState === 'playing' ? (
                <motion.span
                  className="flex items-center gap-1"
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                >
                  <VolumeX size={11} /> {t('stop_btn')}
                </motion.span>
              ) : (
                <><Volume2 size={11} /> {t('listen_btn')}</>
              )}
            </motion.button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

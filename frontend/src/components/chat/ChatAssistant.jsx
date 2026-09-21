import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Send, Trash2, Scale, Volume2, VolumeX, MessageSquare } from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL } from '@/services/i18n'
import { sendChatMessage, clearChatSession, generateTTS } from '@/services/api'
import { Badge, Spinner } from '@/components/ui/index'
import ScalesIcon from '@/components/ui/ScalesIcon'

let _ctr = 0
const uid = () => `msg-${Date.now()}-${_ctr++}`
const sid = () => `session-${Date.now()}-${Math.random().toString(36).slice(2,8)}`

export default function ChatAssistant({ caseContext }) {
  const t = useT()
  const { language, chatSessionId, chatMessages, setChatSessionId, addChatMessage, clearChat } = useAppStore()
  const rtl = isRTL(language)

  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef()

  useEffect(() => {
    if (!chatSessionId) setChatSessionId(sid())
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const sendMessage = async (msg) => {
    if (!msg.trim() || loading) return
    setInput('')
    addChatMessage({ role: 'user', content: msg, id: uid() })
    setLoading(true)
    try {
      const ctx = caseContext ? {
        category:   caseContext.category   || '',
        risk_level: caseContext.risk_level || '',
        summary:    caseContext.summary    || '',
        last_query: '',
      } : {}
      const sessId = chatSessionId || sid()
      const resp = await sendChatMessage(sessId, msg, language, ctx)
      addChatMessage({
        role: 'assistant',
        content: resp.reply,
        confidence: resp.confidence,
        sources: resp.sources || [],
        id: uid(),
      })
    } catch {
      addChatMessage({ role: 'assistant', content: t('chat_error'), id: uid() })
    }
    setLoading(false)
  }

  const handleSend = () => sendMessage(input.trim())

  const handleClear = async () => {
    if (chatSessionId) {
      try { await clearChatSession(chatSessionId) } catch {}
    }
    clearChat()
    setChatSessionId(sid())
  }

  return (
    <div className="card overflow-hidden">
      {/* Header — always LTR for layout */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255,255,255,0.08)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{
              background: 'rgba(124,58,237,0.10)',
              border: '1px solid rgba(124,58,237,0.18)',
            }}
          >
            <MessageSquare size={12} style={{ color: 'rgba(167,139,250,0.70)' }} />
          </div>
          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
            {t('chat_title')}
          </span>
          {caseContext?.category && (
            <Badge variant="primary" className="text-[10px]">{caseContext.category}</Badge>
          )}
        </div>
        <button
          onClick={handleClear}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-xl transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' }}
        >
          <Trash2 size={12} /> {t('chat_clear')}
        </button>
      </div>

      {/* Disclaimer */}
      <div
        className="px-4 py-2 text-xs"
        dir={rtl ? 'rtl' : 'ltr'}
        style={{
          background: 'rgba(234,179,8,0.08)',
          borderBottom: '1px solid rgba(234,179,8,0.18)',
          color: '#fcd34d',
        }}
      >
        {t('chat_disclaimer')}
      </div>

      {/* Messages */}
      <div className="overflow-y-auto px-4 py-4 space-y-4" style={{ maxHeight: 'min(400px, 60vh)' }}>
        {chatMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-4 px-2">
            <Scale size={28} className="mx-auto mb-3 opacity-20" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }} dir={rtl ? 'rtl' : 'ltr'}>
              {t('chat_hint')}
            </p>
            <div className="w-full space-y-2">
              {[t('chat_prompt1'), t('chat_prompt2'), t('chat_prompt3')].map((prompt, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.07 }}
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendMessage(prompt)}
                  className="w-full text-xs px-3 py-2.5 rounded-xl text-left transition-all"
                  dir={rtl ? 'rtl' : 'ltr'}
                  style={{
                    textAlign:   rtl ? 'right' : 'left',
                    background:  'rgba(255,255,255,0.05)',
                    border:      '1px solid rgba(255,255,255,0.09)',
                    color:       'rgba(241,245,249,0.60)',
                    cursor:      'pointer',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background   = 'rgba(255,255,255,0.09)'
                    e.currentTarget.style.borderColor  = 'rgba(255,255,255,0.15)'
                    e.currentTarget.style.color        = 'rgba(241,245,249,0.85)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background   = 'rgba(255,255,255,0.05)'
                    e.currentTarget.style.borderColor  = 'rgba(255,255,255,0.09)'
                    e.currentTarget.style.color        = 'rgba(241,245,249,0.60)'
                  }}
                >
                  💬 {prompt}
                </motion.button>
              ))}
            </div>
          </div>
        ) : (
          chatMessages.map(msg => (
            <ChatMessage key={msg.id} msg={msg} rtl={rtl} language={language} t={t} />
          ))
        )}
        {loading && (
          <div className="flex items-start gap-3">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
              style={{
                background: 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
                boxShadow: '0 0 0 1px rgba(124,58,237,0.40), 0 0 10px rgba(124,58,237,0.45)',
              }}
            >
              <ScalesIcon size={17} gid="cht" />
            </div>
            <div className="rounded-2xl rounded-tl-sm px-4 py-3" style={{ background: 'rgba(255,255,255,0.07)' }}>
              <Spinner size={16} />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t flex items-center gap-2"
        style={{ borderColor: 'rgba(255,255,255,0.08)' }}
      >
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={t('chat_placeholder')}
          dir={rtl ? 'rtl' : 'ltr'}
          className="input flex-1 text-sm"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="btn-primary px-3 py-2 flex-shrink-0"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}

/* ── Chat message row is always dir="ltr" for consistent user/assistant positioning.
   Text direction inside each bubble is set explicitly per message. ── */
function ChatMessage({ msg, rtl, language, t }) {
  const isUser = msg.role === 'user'
  const [ttsState, setTtsState] = useState('idle')
  const audioRef = useRef(null)

  const confLabel = {
    high:   t('conf_high'),
    medium: t('conf_medium'),
    low:    t('conf_low'),
  }

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  const handleListen = async () => {
    if (ttsState === 'playing') {
      audioRef.current?.pause()
      return
    }
    if (ttsState === 'paused') {
      audioRef.current?.play()
      return
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
    } catch {
      setTtsState('idle')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      dir="ltr"
      className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{
          background: isUser
            ? 'linear-gradient(135deg, #7C3AED, #3B82F6)'
            : 'linear-gradient(145deg, #0e1a56 0%, #18106a 40%, #2b0d6e 100%)',
          boxShadow: isUser ? 'none' : '0 0 0 1px rgba(124,58,237,0.40), 0 0 10px rgba(124,58,237,0.40)',
        }}
      >
        {isUser ? '👤' : <ScalesIcon size={17} gid="cma" />}
      </div>

      <div className={`max-w-[80%] space-y-2 flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
          style={{
            background: isUser
              ? 'linear-gradient(135deg, rgba(124,58,237,0.35), rgba(59,130,246,0.35))'
              : 'rgba(255,255,255,0.07)',
            color:     isUser ? '#F1F5F9' : 'var(--text-secondary)',
            border:    isUser ? '1px solid rgba(124,58,237,0.30)' : '1px solid rgba(255,255,255,0.08)',
            direction: rtl ? 'rtl' : 'ltr',
            textAlign: rtl ? 'right' : 'left',
            wordBreak: 'break-word',
          }}
        >
          {msg.content}
        </div>

        {/* Assistant footer: confidence + sources + Listen */}
        {!isUser && (
          <div className="flex flex-wrap items-center gap-1.5">
            {msg.confidence && (
              <span className="badge badge-neutral text-[10px]">
                {msg.confidence === 'high' ? '🟢' : msg.confidence === 'medium' ? '🟡' : '🔴'}{' '}
                {confLabel[msg.confidence] || msg.confidence}
              </span>
            )}
            {msg.sources?.slice(0, 2).map((s, i) => (
              <span key={i} className="badge badge-primary text-[10px]" title={`${(s.score * 100).toFixed(0)}% match`}>
                📜 {s.title?.slice(0, 22)}
              </span>
            ))}

            <motion.button
              onClick={handleListen}
              disabled={ttsState === 'loading'}
              whileTap={{ scale: 0.92 }}
              className="flex items-center gap-1 text-[10px] font-medium rounded-lg px-2 py-1 transition-all"
              style={{
                color:      ttsState === 'playing' ? '#f87171' : 'var(--text-muted)',
                background: ttsState === 'playing' ? 'rgba(239,68,68,0.12)' : 'rgba(255,255,255,0.04)',
                border:     ttsState === 'playing' ? '1px solid rgba(239,68,68,0.25)' : '1px solid rgba(255,255,255,0.08)',
              }}
              onMouseEnter={e => {
                if (ttsState === 'idle' || ttsState === 'paused') {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.14)'
                }
              }}
              onMouseLeave={e => {
                if (ttsState === 'idle' || ttsState === 'paused') {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
                  e.currentTarget.style.color = 'var(--text-muted)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
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

import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, Trash2, Download, Search, Upload, Volume2, ChevronDown, ChevronUp, Scale } from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { analyzeCase, downloadPDF, transcribeAudio, generateTTS } from '@/services/api'
import { RiskBadge, Card, Alert, Spinner, EmptyState, SectionHeader } from '@/components/ui/index'
import NGOList from '@/components/analytics/NGOList'
import SourcesPanel from '@/components/chat/SourcesPanel'
import { PageContainer } from '@/components/layout/PageLayout'

// labelKey maps to i18n qcat_* keys; query object provides language-specific pre-fill text
const CATEGORIES = [
  { icon: '🏠', labelKey: 'qcat_property',    query: { English: 'My landlord is not returning my security deposit and threatening eviction.', Urdu: 'میرا مکان مالک سیکیورٹی ڈپازٹ واپس نہیں کر رہا اور بے دخلی کی دھمکی دے رہا ہے۔' } },
  { icon: '👩', labelKey: 'qcat_family',      query: { English: 'I need information about divorce rights and child custody in Pakistan.', Urdu: 'مجھے پاکستان میں طلاق کے حقوق اور بچوں کی تحویل کے بارے میں معلومات چاہیے۔' } },
  { icon: '💼', labelKey: 'qcat_employment',  query: { English: 'My employer has not paid my salary for 3 months. What are my rights?', Urdu: 'میرے آجر نے 3 ماہ سے تنخواہ نہیں دی۔ میرے کیا حقوق ہیں؟' } },
  { icon: '💻', labelKey: 'qcat_cybercrime',  query: { English: 'Someone is harassing me online and sharing my private photos.', Urdu: 'کوئی آن لائن ہراساں کر رہا ہے اور میری نجی تصاویر شیئر کر رہا ہے۔' } },
  { icon: '🚔', labelKey: 'qcat_criminal',    query: { English: 'Police arrested my family member without warrant. What can I do?', Urdu: 'پولیس نے میرے خاندان کے فرد کو وارنٹ کے بغیر گرفتار کیا۔ میں کیا کر سکتا ہوں؟' } },
  { icon: '💰', labelKey: 'qcat_inheritance', query: { English: 'My siblings are denying me my share of inheritance after my father passed.', Urdu: 'میرے بھائی بہن والد کی وفات کے بعد وراثت میں میرا حصہ دینے سے انکار کر رہے ہیں۔' } },
  { icon: '📝', labelKey: 'qcat_contract',    query: { English: 'The other party is not fulfilling the terms of our written contract.', Urdu: 'دوسرا فریق تحریری معاہدے کی شرائط پوری نہیں کر رہا۔' } },
  { icon: '😡', labelKey: 'qcat_harassment',  query: { English: 'I am facing harassment at workplace. What legal action can I take?', Urdu: 'مجھے کام کی جگہ ہراسانی کا سامنا ہے۔ میں کیا قانونی کارروائی کر سکتا ہوں؟' } },
]

export default function HomePage() {
  const t = useT()
  const { language, city, theme, analysisResult, setAnalysisResult, addToHistory } = useAppStore()
  const rtl = isRTL(language)
  const isDark = theme === 'dark'

  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('laws')
  const [showNGOs, setShowNGOs] = useState(false)
  const [ttsTarget, setTtsTarget] = useState(null)   // null | 'summary' | 'laws' | 'rights' | 'steps'
  const [recording, setRecording] = useState(false)
  const [recordLoading, setRecordLoading] = useState(false)
  const [recordError, setRecordError] = useState('')
  const fileRef = useRef()
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  const handleAnalyze = async () => {
    if (!query.trim() || query.length < 15) {
      setError(t('err_min_chars'))
      return
    }
    setError('')
    setLoading(true)
    try {
      const result = await analyzeCase(query.trim(), language, city)
      setAnalysisResult(result)
      addToHistory({ query: query.trim(), result, timestamp: Date.now() })
    } catch (err) {
      setError(err.response?.data?.detail || 'Analysis failed. Check if the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setQuery('')
    setAnalysisResult(null)
    setError('')
  }

  const handleDownloadPDF = async () => {
    if (!analysisResult) return
    try {
      const blob = await downloadPDF(analysisResult, language)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'legal_report.pdf'; a.click()
      URL.revokeObjectURL(url)
    } catch {}
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    try {
      const { extractTextFromFile } = await import('@/services/fileParser')
      const text = await extractTextFromFile(file)
      const trimmed = text?.trim() || ''
      if (trimmed) {
        setQuery(trimmed.slice(0, 2000))
      } else {
        setError(t('file_no_text'))
      }
    } catch (err) {
      setError(err.message || t('file_error'))
    } finally {
      e.target.value = ''
    }
  }

  const handleRecord = async () => {
    if (recording) {
      mediaRecorderRef.current?.stop()
      return
    }
    setRecordError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        setRecording(false)
        setRecordLoading(true)
        try {
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
          const result = await transcribeAudio(blob, language)
          if (result?.text) setQuery(result.text)
        } catch {
          setRecordError(t('err_transcribe'))
        } finally {
          setRecordLoading(false)
        }
      }

      mediaRecorder.start()
      setRecording(true)
    } catch {
      setRecordError(t('err_mic'))
    }
  }

  const handleTTS = async (text, target = 'summary') => {
    if (!text?.trim() || ttsTarget) return
    setTtsTarget(target)
    try {
      const blob = await generateTTS(text, language)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.play()
      audio.onended = () => URL.revokeObjectURL(url)
    } catch {}
    setTtsTarget(null)
  }

  const res = analysisResult

  return (
    <PageContainer size="full">
      {/* Hero */}
      <SectionHeader
        eyebrow="AI-POWERED LEGAL ASSISTANCE"
        title="Pakistan AI Legal Aid Assistant"
        description="Chat • Analyze Documents • Connect with Legal Support"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── LEFT: Input Panel ── */}
        <div className="space-y-4">
          <Card padding="p-5">
            <div className="label mb-2">{t('input_label')}</div>

            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={t('input_placeholder')}
              rows={7}
              dir={rtl ? 'rtl' : 'ltr'}
              className="input resize-none text-sm leading-relaxed"
            />

            <div className="flex items-center justify-between mt-1">
              <span className="text-xs font-mono" style={{ color: query.length > 2000 ? 'var(--danger-text)' : 'var(--text-muted)' }}>
                {query.length} / 2000
              </span>
              {query.length > 0 && query.length < 15 && (
                <span className="text-xs" style={{ color: 'var(--warning-text)' }}>{t('min_chars')}</span>
              )}
            </div>

            {/* Action row */}
            <div className="flex items-center gap-2 mt-3">
              {/* Voice record */}
              <button
                onClick={handleRecord}
                disabled={recordLoading}
                className="btn-outline px-3 py-2 text-xs gap-1.5 flex items-center"
                title={recording ? t('title_record_stop') : t('title_record_start')}
                style={recording ? { borderColor: '#ef4444', color: '#f87171' } : {}}
              >
                {recordLoading ? (
                  <Spinner size={14} />
                ) : recording ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    {t('btn_stop')}
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5"><Mic size={14} /> {t('btn_record')}</span>
                )}
              </button>

              <button onClick={handleClear} className="btn-outline px-3 py-2 text-xs" title={t('clear_btn')}>
                <Trash2 size={14} />
              </button>

              <button
                onClick={handleDownloadPDF}
                className="btn-outline px-3 py-2 text-xs"
                title={t('download_btn')}
                disabled={!res}
              >
                <Download size={14} />
              </button>

              {/* Upload doc */}
              <button
                onClick={() => fileRef.current?.click()}
                className="btn-outline px-3 py-2 text-xs gap-1.5"
                title={t('title_upload')}
              >
                <Upload size={14} /> {t('btn_upload')}
              </button>
              <input ref={fileRef} type="file" accept=".txt,.pdf,.docx" className="hidden" onChange={handleFileUpload} />

              <button
                onClick={handleAnalyze}
                disabled={loading || query.length < 15}
                className="btn-primary py-2 text-sm ml-auto"
              >
                {loading ? <Spinner size={16} /> : <Search size={15} />}
                {loading ? t('analyzing_btn') : t('analyze_btn')}
              </button>
            </div>
          </Card>

          {error && (
            <Alert type="danger">⚠️ {error}</Alert>
          )}

          {recordError && (
            <Alert type="danger">🎙️ {recordError}</Alert>
          )}

          {/* Quick categories */}
          <Card padding="p-4">
            <div className="label mb-3">{t('categories_label')}</div>
            <div className="grid grid-cols-2 gap-2">
              {CATEGORIES.map((cat, i) => (
                <motion.button
                  key={i}
                  whileHover={{ scale: 1.015, y: -2 }}
                  whileTap={{ scale: 0.97, y: 0 }}
                  onClick={() => setQuery(cat.query[language] || cat.query.English)}
                  className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-left transition-all duration-150"
                  style={isDark
                    ? { background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', border: '1px solid rgba(255,255,255,0.09)' }
                    : { background: '#F8FAFC', color: 'var(--text-secondary)', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }
                  }
                  onMouseEnter={e => {
                    if (isDark) {
                      e.currentTarget.style.background = 'rgba(124,58,237,0.12)'
                      e.currentTarget.style.borderColor = 'rgba(124,58,237,0.25)'
                      e.currentTarget.style.boxShadow = ''
                    } else {
                      e.currentTarget.style.background = '#F1F5F9'
                      e.currentTarget.style.borderColor = 'rgba(124,58,237,0.40)'
                      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124,58,237,0.08), 0 1px 4px rgba(0,0,0,0.08)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (isDark) {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                      e.currentTarget.style.borderColor = 'rgba(255,255,255,0.09)'
                      e.currentTarget.style.boxShadow = ''
                    } else {
                      e.currentTarget.style.background = '#F8FAFC'
                      e.currentTarget.style.borderColor = '#E2E8F0'
                      e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
                    }
                  }}
                >
                  <span className="text-base">{cat.icon}</span>
                  <span>{t(cat.labelKey)}</span>
                </motion.button>
              ))}
            </div>
          </Card>
        </div>

        {/* ── RIGHT: Results Panel ── */}
        <div className="space-y-4">
          <div className="label">{t('results_label')}</div>

          {!res && !loading && (
            <EmptyState
              icon={<Scale size={44} style={{ color: 'rgba(139,92,246,0.38)', display: 'block', margin: '0 auto' }} />}
              title={t('no_results_title')}
              description={t('no_results')}
            />
          )}

          {loading && (
            <Card padding="p-8">
              <div className="flex flex-col items-center gap-3">
                <Spinner size={32} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('loading')}</p>
              </div>
            </Card>
          )}

          {res && !loading && (
            <AnimatePresence mode="wait">
              <motion.div
                key="result"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                {/* Urgent helplines */}
                {res.urgent_helplines?.length > 0 && (
                  <div className="rounded-xl border-l-4 p-4"
                       style={{ background: 'rgba(239,68,68,0.10)', borderColor: '#ef4444' }}>
                    <div className="font-bold text-sm mb-2" style={{ color: '#f87171' }}>
                      🚨 {t('urgent_helplines')}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {res.urgent_helplines.map((h, i) => (
                        <span key={i} className="rounded-xl px-3 py-1 text-xs font-semibold"
                              style={{ background: 'rgba(239,68,68,0.22)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.35)' }}>
                          {h.icon} {h.label}: {h.number}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Category + Risk + Confidence */}
                <Card padding="p-5" className="card-important">
                  {/* Primary: detected category */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <div
                        className="text-[10px] font-bold uppercase tracking-widest mb-2"
                        style={{ color: 'var(--text-muted)', letterSpacing: '0.09em' }}
                      >
                        {t('detected_category')}
                      </div>
                      <div className="flex items-center gap-2">
                        <div
                          className="flex-shrink-0 flex items-center justify-center rounded-lg"
                          style={{
                            width: 28, height: 28,
                            background: 'rgba(124,58,237,0.12)',
                            color: '#a78bfa',
                          }}
                        >
                          <Scale size={14} />
                        </div>
                        <div className="text-[17px] font-semibold leading-tight" style={{ color: 'var(--text-primary)' }}>
                          {translateCategory(res.category, language)}
                        </div>
                      </div>
                    </div>
                    {/* Secondary: risk badge — right-aligned, visually subordinate */}
                    <div className="flex-shrink-0 pt-0.5">
                      <RiskBadge level={res.risk_level} />
                    </div>
                  </div>

                  {/* Confidence bar — driven by actual source score from backend */}
                  {(() => {
                    const topScore = res.sources?.[0]?.score         // FAISS cosine similarity (0–1)
                    const pct      = topScore != null ? Math.round(topScore * 100) : null
                    const confKey  = (res.confidence || '').charAt(0).toUpperCase() + (res.confidence || '').slice(1)
                    const label    = pct != null ? `${pct}% ${t('pct_match')}` : `${confKey} ${t('pct_match')}`
                    const barColor = pct != null
                      ? (pct >= 70 ? '#10B981' : pct >= 45 ? '#F59E0B' : '#F87171')
                      : ({ High: '#10B981', Medium: '#F59E0B', Low: '#F87171' }[confKey] ?? '#F59E0B')
                    const barW = pct != null
                      ? `${pct}%`
                      : ({ High: '80%', Medium: '52%', Low: '26%' }[confKey] ?? '50%')
                    return (
                      <div className="flex items-center gap-3" dir="ltr">
                        <div
                          className="flex-1 rounded-full overflow-hidden"
                          style={{ height: 5, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)' }}
                        >
                          <div
                            style={{
                              width: barW, height: '100%',
                              background: barColor, borderRadius: 9999,
                              transition: 'width 0.6s ease',
                            }}
                          />
                        </div>
                        <span
                          className="text-[11px] font-semibold font-mono flex-shrink-0"
                          style={{ color: 'var(--text-muted)', minWidth: 76, textAlign: 'right' }}
                        >
                          {label}
                        </span>
                      </div>
                    )
                  })()}

                  {/* Risk reason */}
                  {res.risk_reason && (
                    <p className="text-xs mt-3 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                      {res.risk_reason}
                    </p>
                  )}
                </Card>

                {/* Summary */}
                <Card padding="p-4" className="card-important">
                  <div className="flex items-center justify-between mb-2">
                    <div className="label">{t('summary_label')}</div>
                    <button
                      onClick={() => handleTTS(res.summary, 'summary')}
                      disabled={!!ttsTarget}
                      className="flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1 transition-all"
                      style={{
                        color: ttsTarget === 'summary' ? '#a78bfa' : 'var(--text-muted)',
                        background: ttsTarget === 'summary' ? 'rgba(124,58,237,0.10)' : 'transparent',
                      }}
                    >
                      <Volume2 size={13} /> {ttsTarget === 'summary' ? t('loading_tts') : t('listen_btn')}
                    </button>
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)', direction: rtl ? 'rtl' : 'ltr' }}>
                    {res.summary}
                  </p>
                </Card>

                {/* Tabs */}
                <Card padding="p-0" className="card-important">
                  <div className="flex items-center border-b pr-3" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
                    {['laws','rights','steps','sources'].map(tab => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className="px-4 py-3 text-xs font-semibold capitalize border-b-2 transition-colors"
                        style={{
                          borderColor: activeTab === tab ? '#7C3AED' : 'transparent',
                          color: activeTab === tab ? '#a78bfa' : 'var(--text-muted)',
                        }}
                      >
                        {{ laws: t('tab_laws'), rights: t('tab_rights'), steps: t('tab_steps'), sources: t('tab_sources') }[tab]}
                      </button>
                    ))}

                    {/* Per-tab Listen button — hidden for Sources */}
                    {activeTab !== 'sources' && (() => {
                      const tabText = {
                        laws:   res.laws?.join(language === 'Urdu' ? '۔ ' : '. '),
                        rights: res.rights?.join(language === 'Urdu' ? '۔ ' : '. '),
                        steps:  res.next_steps?.join(language === 'Urdu' ? '۔ ' : '. '),
                      }[activeTab] || ''
                      const isActive = ttsTarget === activeTab
                      return (
                        <button
                          onClick={() => handleTTS(tabText, activeTab)}
                          disabled={!!ttsTarget || !tabText}
                          className="ml-auto flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 flex-shrink-0 transition-all"
                          style={{
                            color: isActive ? '#a78bfa' : 'var(--text-muted)',
                            background: isActive ? 'rgba(124,58,237,0.10)' : 'transparent',
                            border: isActive ? '1px solid rgba(124,58,237,0.20)' : '1px solid transparent',
                          }}
                          title={t('listen_btn')}
                        >
                          <Volume2 size={12} />
                          {isActive ? t('loading_tts') : t('listen_btn')}
                        </button>
                      )
                    })()}
                  </div>
                  <div className="p-4">
                    {activeTab === 'laws' && <BulletList items={res.laws} icon="📜" color="#7C3AED" />}
                    {activeTab === 'rights' && <BulletList items={res.rights} icon="✅" color="#10B981" />}
                    {activeTab === 'steps' && <BulletList items={res.next_steps} icon="👣" color="#22D3EE" />}
                    {activeTab === 'sources' && <SourcesPanel sources={res.sources} language={language} />}
                  </div>
                </Card>

                {/* NGOs toggle */}
                {res.ngos?.length > 0 && (
                  <Card padding="p-0">
                    <button
                      onClick={() => setShowNGOs(v => !v)}
                      className="flex items-center justify-between w-full px-4 py-3 text-sm font-semibold"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      <span>🏢 {t('ngos_for')} {translateCategory(res.category, language)} ({res.ngos.length})</span>
                      {showNGOs ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <AnimatePresence>
                      {showNGOs && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden px-4 pb-4"
                        >
                          <NGOList ngos={res.ngos} caseType={res.category} />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-10 text-center text-xs py-6" style={{ color: 'var(--text-muted)', borderTop: '1px solid rgba(255,255,255,0.07)' }}>
        {t('disclaimer')}
      </div>
    </PageContainer>
  )
}

function BulletList({ items, icon, color }) {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)
  if (!items?.length) return <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('no_info')}</p>
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: rtl ? 8 : -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className="flex items-start gap-2 text-sm leading-relaxed"
          style={{ color: 'var(--text-secondary)' }}
        >
          <span className="flex-shrink-0 mt-0.5">{icon}</span>
          <span style={{ direction: rtl ? 'rtl' : 'ltr', textAlign: rtl ? 'right' : 'left' }}>{item}</span>
        </motion.li>
      ))}
    </ul>
  )
}

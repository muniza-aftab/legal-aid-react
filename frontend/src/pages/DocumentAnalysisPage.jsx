import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, Scale, Clock, ArrowRight, X, AlertCircle,
  Image, Shield, Globe, BookOpen, ChevronDown, ChevronUp,
} from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL } from '@/services/i18n'
import { SectionHeader, Card, Spinner, Alert } from '@/components/ui/index'

// ── Constants ──────────────────────────────────────────────────────────────────
const MAX_BYTES   = 10 * 1024 * 1024
const PREVIEW_CAP = 2000

const TEXT_MIME  = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]
const IMAGE_MIME = ['image/png', 'image/jpeg']

const CONFIDENCE_COLOR = { High: '#34d399', Medium: '#fbbf24', Low: '#f87171' }
const CONFIDENCE_BG    = { High: 'rgba(52,211,153,0.12)', Medium: 'rgba(251,191,36,0.12)', Low: 'rgba(248,113,113,0.12)' }

const ALL_OPEN = { summary: true, keyPoints: true, procedural: true, deadlines: true, risks: true, laws: true, urdu: true }

const isImageFile = (f) => IMAGE_MIME.includes(f?.type) || /\.(png|jpe?g)$/i.test(f?.name ?? '')
const isTextFile  = (f) => TEXT_MIME.includes(f?.type)  || /\.(pdf|docx|txt)$/i.test(f?.name ?? '')

function formatBytes(bytes) {
  if (bytes < 1024)         return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── Sub-components ─────────────────────────────────────────────────────────────

/**
 * Animated bullet list — mirrors the pattern from HomePage's BulletList.
 * Each item enters from the appropriate side (RTL-aware) and uses dir="auto"
 * so the browser detects base direction for mixed Urdu/English strings.
 */
function BulletList({ items, emptyKey, t, rtl }) {
  if (!items || items.length === 0) {
    return (
      <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
        {t(emptyKey)}
      </p>
    )
  }
  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: rtl ? 8 : -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.045, duration: 0.18 }}
          className="flex items-start gap-2 text-sm leading-relaxed"
        >
          <span
            aria-hidden
            className="flex-shrink-0 mt-0.5 font-bold"
            style={{ color: '#818cf8', fontSize: 15, lineHeight: 1.4 }}
          >
            ›
          </span>
          {/* dir="auto" lets the browser infer per-item direction for mixed content */}
          <span dir="auto" style={{ color: 'var(--text-secondary)' }}>
            {item}
          </span>
        </motion.li>
      ))}
    </ul>
  )
}

/**
 * Law citation list — styled differently from bullet list; each entry gets
 * a subtle tinted background matching the section accent colour.
 */
function LawList({ items, emptyKey, t }) {
  if (!items || items.length === 0) {
    return (
      <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
        {t(emptyKey)}
      </p>
    )
  }
  return (
    <ul className="space-y-2">
      {items.map((law, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06, duration: 0.18 }}
          className="text-xs leading-relaxed px-3 py-2.5 rounded-xl"
          style={{
            background: 'rgba(167,139,250,0.07)',
            border: '1px solid rgba(167,139,250,0.14)',
            color: 'var(--text-secondary)',
          }}
          dir="auto"
        >
          {law}
        </motion.li>
      ))}
    </ul>
  )
}

/**
 * Collapsible section card — replicates the NGO-toggle pattern from HomePage.
 * Header is always visible; content animates via height: 0 → auto.
 */
function CollapsibleSection({ titleKey, Icon, color, bg, isOpen, onToggle, children, t, rtl }) {
  return (
    <Card padding="p-0" className="card-important">
      {/* Clickable header */}
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center justify-between w-full px-5 py-4 transition-colors"
        style={{ color: 'var(--text-primary)', textAlign: rtl ? 'right' : 'left' }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: bg, border: `1px solid ${color}30` }}
          >
            <Icon size={14} style={{ color }} />
          </div>
          <span className="label" style={{ fontSize: 11 }}>{t(titleKey)}</span>
        </div>
        <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </span>
      </button>

      {/* Animated body */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function DocumentAnalysisPage() {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)

  // Upload / extraction state
  const [file,            setFile]            = useState(null)
  const [isDragging,      setIsDragging]      = useState(false)
  const [validationError, setValidationError] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [isExtracting,    setIsExtracting]    = useState(false)
  const [extractedText,   setExtractedText]   = useState(null)
  const [extractError,    setExtractError]    = useState('')

  // AI analysis state
  const [isAnalyzing,   setIsAnalyzing]   = useState(false)
  const [analysis,      setAnalysis]      = useState(null)
  const [analysisError, setAnalysisError] = useState('')

  // Collapsible section open/closed state — all open by default
  const [openSections, setOpenSections] = useState(ALL_OPEN)
  const toggleSection = useCallback(
    (key) => setOpenSections(s => ({ ...s, [key]: !s[key] })),
    [],
  )

  const fileInputRef = useRef(null)

  // Revoke blob URL on cleanup
  useEffect(
    () => () => { if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl) },
    [imagePreviewUrl],
  )

  // ── File handling ──────────────────────────────────────────────────────────
  const processFile = useCallback(async (f) => {
    // Reset all derived state first
    setValidationError('')
    setFile(null)
    setImagePreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return '' })
    setExtractedText(null)
    setExtractError('')
    setIsExtracting(false)
    setAnalysis(null)
    setAnalysisError('')
    setOpenSections(ALL_OPEN)

    if (!isImageFile(f) && !isTextFile(f)) { setValidationError(t('doc_validation_type')); return }
    if (f.size > MAX_BYTES)                { setValidationError(t('doc_validation_size'));  return }

    setFile(f)

    if (isImageFile(f)) { setImagePreviewUrl(URL.createObjectURL(f)); return }

    // Local text extraction for preview (PDF / DOCX / TXT)
    setIsExtracting(true)
    try {
      const { extractTextFromFile } = await import('@/services/fileParser')
      const raw = await extractTextFromFile(f)
      setExtractedText(raw?.trim() ?? '')
    } catch (err) {
      setExtractError(err.message || t('doc_extract_error'))
    } finally {
      setIsExtracting(false)
    }
  }, [t])

  const handleFile    = useCallback((f) => { if (f) processFile(f) }, [processFile])
  const onDrop        = useCallback((e) => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files?.[0]) }, [handleFile])
  const onDragOver    = useCallback((e) => { e.preventDefault(); setIsDragging(true)  }, [])
  const onDragLeave   = useCallback(() => setIsDragging(false), [])
  const onInputChange = (e) => { handleFile(e.target.files?.[0]); e.target.value = '' }

  const clearFile = () => {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl)
    setFile(null); setImagePreviewUrl(''); setExtractedText(null)
    setExtractError(''); setValidationError(''); setIsExtracting(false)
    setAnalysis(null); setAnalysisError(''); setOpenSections(ALL_OPEN)
  }

  // ── Backend analysis call ──────────────────────────────────────────────────
  const analyzeDocument = useCallback(async () => {
    if (!file || isAnalyzing) return
    setIsAnalyzing(true)
    setAnalysisError('')
    setAnalysis(null)
    setOpenSections(ALL_OPEN)   // reset sections on re-analysis

    const formData = new FormData()
    formData.append('file', file)
    formData.append('language', language)

    try {
      const resp = await fetch('/api/analyze-document', { method: 'POST', body: formData })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || t('doc_analysis_error'))
      }
      setAnalysis(await resp.json())
    } catch (err) {
      setAnalysisError(err.message || t('doc_analysis_error'))
    } finally {
      setIsAnalyzing(false)
    }
  }, [file, isAnalyzing, language, t])

  // ── Derived values ─────────────────────────────────────────────────────────
  const previewText = (extractedText || '').slice(0, PREVIEW_CAP)
  const isTruncated = (extractedText?.length ?? 0) > PREVIEW_CAP
  const charCount   =  extractedText?.length ?? 0
  const la          = analysis?.legal_analysis    // shorthand for legal_analysis object
  const canAnalyze  = file && !isExtracting && !isAnalyzing

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto px-4 py-6" dir={rtl ? 'rtl' : 'ltr'}>
      <SectionHeader
        eyebrow={t('doc_eyebrow')}
        title={t('doc_title')}
        description={t('doc_sub')}
      />

      {/* ── Upload zone ─────────────────────────────────────────────────────── */}
      <div
        onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
        className="mb-3 rounded-2xl transition-all duration-200"
        style={{
          border:     isDragging ? '2px dashed #7C3AED' : '2px dashed rgba(255,255,255,0.12)',
          background: isDragging ? 'rgba(124,58,237,0.06)' : 'rgba(255,255,255,0.02)',
          padding: '2.5rem 1.5rem',
          textAlign: 'center',
          cursor: file ? 'default' : 'pointer',
        }}
        onClick={() => { if (!file) fileInputRef.current?.click() }}
      >
        <input
          ref={fileInputRef} type="file"
          accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
          className="hidden" onChange={onInputChange}
        />

        <AnimatePresence mode="wait">
          {file ? (
            /* File selected */
            <motion.div
              key="file-selected"
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              className="flex flex-col items-center gap-3"
            >
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{
                  background: isImageFile(file) ? 'rgba(52,211,153,0.12)' : 'rgba(129,140,248,0.12)',
                  border:     isImageFile(file) ? '1px solid rgba(52,211,153,0.20)' : '1px solid rgba(129,140,248,0.20)',
                }}
              >
                {isImageFile(file)
                  ? <Image    size={26} style={{ color: '#34d399' }} />
                  : <FileText size={26} style={{ color: '#818cf8' }} />
                }
              </div>

              {/* Filename + size — always LTR so paths don't mirror */}
              <div>
                <div
                  className="font-semibold text-sm mb-1"
                  style={{ color: 'var(--text-primary)' }}
                  dir="ltr"
                >
                  {file.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {formatBytes(file.size)}
                </div>
              </div>

              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); clearFile() }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs transition-colors"
                style={{ color: 'var(--text-muted)', border: '1px solid rgba(255,255,255,0.10)' }}
                onMouseEnter={e => {
                  e.currentTarget.style.color       = '#f87171'
                  e.currentTarget.style.borderColor = 'rgba(248,113,113,0.30)'
                  e.currentTarget.style.background  = 'rgba(248,113,113,0.07)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.color       = 'var(--text-muted)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.10)'
                  e.currentTarget.style.background  = 'transparent'
                }}
              >
                <X size={12} />
                {language === 'Urdu' ? 'ہٹائیں' : 'Remove'}
              </button>
            </motion.div>
          ) : (
            /* Drop / browse prompt */
            <motion.div
              key="upload-prompt"
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            >
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{
                  background: isDragging ? 'rgba(124,58,237,0.16)' : 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.09)',
                  transition: 'background 0.2s',
                }}
              >
                <Upload
                  size={24}
                  style={{ color: isDragging ? '#a78bfa' : 'rgba(255,255,255,0.35)', transition: 'color 0.2s' }}
                />
              </div>
              <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                {t('doc_upload_hint')}
              </p>
              <p className="text-xs mb-5" style={{ color: 'var(--text-muted)' }}>
                {t('doc_supported_files')}
              </p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}
                className="btn-primary py-2"
              >
                {t('doc_upload_label')}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Validation error */}
      <AnimatePresence>
        {validationError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            className="mb-4"
          >
            <Alert type="danger">
              <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
              <span>{validationError}</span>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {!file ? (
          /* Pre-upload empty state */
          <motion.div
            key="pre-upload"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-14 text-center"
          >
            <div className="text-5xl mb-4" style={{ opacity: 0.28 }}>📄</div>
            <p className="font-semibold text-base mb-1" style={{ color: 'var(--text-primary)' }}>
              {t('doc_empty_title')}
            </p>
            <p className="text-sm max-w-xs" style={{ color: 'var(--text-muted)' }}>
              {t('doc_empty_desc')}
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="file-content"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="space-y-3"
          >
            {/* ── Text / image preview ──────────────────────────────────────── */}
            <Card padding="p-5">
              <div className="label mb-3">
                {isImageFile(file) ? t('doc_image_preview') : t('doc_preview_label')}
              </div>

              {isImageFile(file) ? (
                <div className="flex flex-col items-center gap-4">
                  <img
                    src={imagePreviewUrl} alt={file.name}
                    className="max-h-56 max-w-full rounded-xl object-contain"
                    style={{ border: '1px solid rgba(255,255,255,0.08)' }}
                  />
                  <Alert type="info" className="w-full">
                    <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                    <span>{t('doc_image_ocr_note')}</span>
                  </Alert>
                </div>

              ) : isExtracting ? (
                <div className="flex items-center gap-3 py-8 justify-center" style={{ color: 'var(--text-muted)' }}>
                  <Spinner size={18} />
                  <span className="text-sm">{t('doc_extracting')}</span>
                </div>

              ) : extractError ? (
                <Alert type="warning">
                  <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                  <span>{extractError}</span>
                </Alert>

              ) : extractedText !== null && extractedText === '' ? (
                <Alert type="warning">
                  <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                  <span>{t('doc_no_text')}</span>
                </Alert>

              ) : extractedText ? (
                <>
                  {/* Meta row — always LTR so numbers don't mirror in RTL layouts */}
                  <div
                    className="flex items-center justify-between mb-2 text-xs"
                    style={{ color: 'var(--text-muted)' }}
                    dir="ltr"
                  >
                    <span>{charCount.toLocaleString()} {t('doc_preview_chars')}</span>
                    {isTruncated && <span className="italic">{t('doc_preview_truncated')}</span>}
                  </div>
                  {/* Scrollable text — dir="auto" for mixed Urdu / English content */}
                  <div
                    className="rounded-xl p-3 text-xs leading-relaxed overflow-y-auto"
                    style={{
                      maxHeight: 180,
                      background: 'rgba(0,0,0,0.20)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      color: 'var(--text-muted)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'monospace',
                    }}
                    dir="auto"
                  >
                    {previewText}
                    {isTruncated && <span style={{ fontStyle: 'italic' }}> …</span>}
                  </div>
                </>
              ) : null}
            </Card>

            {/* ── Analyse button ────────────────────────────────────────────── */}
            {!isAnalyzing && (
              <div className="flex justify-center pt-1">
                <button
                  type="button"
                  onClick={analyzeDocument}
                  disabled={!canAnalyze}
                  className="btn-primary py-2.5"
                >
                  <Scale size={15} />
                  {analysis ? t('doc_reanalyze_btn') : t('doc_analyze_btn')}
                </button>
              </div>
            )}

            {/* Analysis loading */}
            {isAnalyzing && (
              <Card padding="p-7">
                <div className="flex flex-col items-center gap-3">
                  <Spinner size={28} />
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    {t('doc_analyzing')}
                  </p>
                </div>
              </Card>
            )}

            {/* Analysis error */}
            {analysisError && (
              <Alert type="danger">
                <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                <span>{analysisError}</span>
              </Alert>
            )}

            {/* ── Analysis results ─────────────────────────────────────────── */}
            <AnimatePresence>
              {analysis && !isAnalyzing && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-3"
                >
                  {/* ── Meta row: document type + confidence + language ─────── */}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    {analysis.document_type && analysis.document_type !== 'Unknown' && (
                      <span
                        className="px-3 py-1 rounded-full text-xs font-semibold"
                        style={{
                          background: 'rgba(129,140,248,0.14)',
                          color: '#818cf8',
                          border: '1px solid rgba(129,140,248,0.24)',
                        }}
                      >
                        {t('doc_doc_type_label')}: {analysis.document_type}
                      </span>
                    )}

                    {la?.confidence && (
                      <span
                        className="px-3 py-1 rounded-full text-xs font-semibold"
                        style={{
                          background: CONFIDENCE_BG[la.confidence]  ?? CONFIDENCE_BG.Medium,
                          color:      CONFIDENCE_COLOR[la.confidence] ?? CONFIDENCE_COLOR.Medium,
                          border:     `1px solid ${CONFIDENCE_COLOR[la.confidence] ?? CONFIDENCE_COLOR.Medium}35`,
                        }}
                      >
                        {t('doc_confidence_label')}: {la.confidence}
                      </span>
                    )}

                    {analysis.detected_language && (
                      <span
                        className="px-3 py-1 rounded-full text-xs"
                        style={{
                          background: 'rgba(255,255,255,0.05)',
                          color: 'var(--text-muted)',
                          border: '1px solid rgba(255,255,255,0.09)',
                        }}
                      >
                        {analysis.detected_language}
                      </span>
                    )}
                  </div>

                  {/* Extraction succeeded but LLM analysis was skipped (text too short) */}
                  {analysis.legal_analysis === null && (
                    <Alert type="info">
                      <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                      <span>
                        {language === 'Urdu'
                          ? 'متن نکالا گیا لیکن یہ تجزیہ کے لیے کافی نہیں ہے۔ ایک مزید مکمل دستاویز آزمائیں۔'
                          : 'Text was extracted but was too short for AI analysis. Try a more complete document.'}
                      </span>
                    </Alert>
                  )}

                  {/* LLM error notice (analysis ran but returned an error) */}
                  {la?.error && (
                    <Alert type="warning">
                      <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                      <span>{la.error}</span>
                    </Alert>
                  )}

                  {/* ── Summary (collapsible) ─────────────────────────────── */}
                  {la?.summary && (
                    <CollapsibleSection
                      titleKey="doc_summary_title"
                      Icon={FileText}
                      color="#818cf8"
                      bg="rgba(129,140,248,0.10)"
                      isOpen={openSections.summary}
                      onToggle={() => toggleSection('summary')}
                      t={t}
                      rtl={rtl}
                    >
                      {/* dir="auto": browser detects base direction per paragraph */}
                      <p
                        className="text-sm leading-relaxed"
                        style={{ color: 'var(--text-secondary)' }}
                        dir="auto"
                      >
                        {la.summary}
                      </p>
                    </CollapsibleSection>
                  )}

                  {/* Analysis sections — only rendered when analysis completed without a fatal error */}
                  {la && !la.error && (
                    <>
                  {/* ── Key legal points (collapsible) ───────────────────── */}
                  <CollapsibleSection
                    titleKey="doc_key_points_title"
                    Icon={Scale}
                    color="#34d399"
                    bg="rgba(52,211,153,0.10)"
                    isOpen={openSections.keyPoints}
                    onToggle={() => toggleSection('keyPoints')}
                    t={t}
                    rtl={rtl}
                  >
                    <BulletList items={la?.key_legal_points} emptyKey="doc_none_found" t={t} rtl={rtl} />
                  </CollapsibleSection>

                  {/* ── Procedural guidance (collapsible) ────────────────── */}
                  <CollapsibleSection
                    titleKey="doc_procedural_title"
                    Icon={ArrowRight}
                    color="#f9a8d4"
                    bg="rgba(249,168,212,0.10)"
                    isOpen={openSections.procedural}
                    onToggle={() => toggleSection('procedural')}
                    t={t}
                    rtl={rtl}
                  >
                    <BulletList items={la?.procedural_guidance} emptyKey="doc_none_found" t={t} rtl={rtl} />
                  </CollapsibleSection>

                  {/* ── Deadlines (collapsible) ──────────────────────────── */}
                  <CollapsibleSection
                    titleKey="doc_deadlines_title"
                    Icon={Clock}
                    color="#fbbf24"
                    bg="rgba(251,191,36,0.10)"
                    isOpen={openSections.deadlines}
                    onToggle={() => toggleSection('deadlines')}
                    t={t}
                    rtl={rtl}
                  >
                    <BulletList items={la?.deadlines} emptyKey="doc_none_found" t={t} rtl={rtl} />
                  </CollapsibleSection>

                  {/* ── Risk indicators (collapsible) ────────────────────── */}
                  <CollapsibleSection
                    titleKey="doc_risk_title"
                    Icon={Shield}
                    color="#f87171"
                    bg="rgba(248,113,113,0.10)"
                    isOpen={openSections.risks}
                    onToggle={() => toggleSection('risks')}
                    t={t}
                    rtl={rtl}
                  >
                    <BulletList items={la?.risk_indicators} emptyKey="doc_none_found" t={t} rtl={rtl} />
                  </CollapsibleSection>

                  {/* ── Referenced laws — only rendered when backend returned items */}
                  {la?.cited_laws?.length > 0 && (
                    <CollapsibleSection
                      titleKey="doc_laws_title"
                      Icon={BookOpen}
                      color="#a78bfa"
                      bg="rgba(167,139,250,0.10)"
                      isOpen={openSections.laws}
                      onToggle={() => toggleSection('laws')}
                      t={t}
                      rtl={rtl}
                    >
                      <LawList items={la.cited_laws} emptyKey="doc_none_found" t={t} />
                    </CollapsibleSection>
                  )}
                    </>
                  )}

                  {/* ── Urdu explanation (collapsible) ───────────────────── */}
                  {la?.urdu_explanation && (
                    <CollapsibleSection
                      titleKey="doc_urdu_title"
                      Icon={Globe}
                      color="#fbbf24"
                      bg="rgba(251,191,36,0.10)"
                      isOpen={openSections.urdu}
                      onToggle={() => toggleSection('urdu')}
                      t={t}
                      rtl={rtl}
                    >
                      {/*
                        Always force RTL for Urdu text regardless of UI language.
                        line-height 1.9 gives comfortable reading for Nastaliq-style fonts.
                      */}
                      <p
                        className="text-sm"
                        style={{ color: 'var(--text-secondary)', lineHeight: 1.9, direction: 'rtl', textAlign: 'right' }}
                      >
                        {la.urdu_explanation}
                      </p>
                    </CollapsibleSection>
                  )}

                  {/* ── Disclaimer ────────────────────────────────────────── */}
                  <Card padding="p-4">
                    <p
                      className="text-xs text-center"
                      style={{ color: 'var(--text-muted)' }}
                      dir="auto"
                    >
                      {la?.disclaimer || t('doc_disclaimer')}
                    </p>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Pre-analysis hint (shown while file is loaded but no analysis yet) */}
            {!analysis && !isAnalyzing && !analysisError && (
              <p className="text-xs text-center py-2" style={{ color: 'var(--text-muted)' }}>
                {t('doc_disclaimer')}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

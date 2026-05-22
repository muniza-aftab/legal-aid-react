import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, Scale, Clock, X, AlertCircle,
  Image, Shield, Globe, BookOpen, CheckCircle, ArrowRight,
  ChevronDown, ChevronUp,
} from 'lucide-react'
import { useAppStore } from '@/services/store'
import { useT, isRTL } from '@/services/i18n'
import { SectionHeader, Card, Spinner, Alert } from '@/components/ui/index'

// ── Constants ──────────────────────────────────────────────────────────────────
const MAX_BYTES  = 10 * 1024 * 1024
const PREVIEW_CAP = 2000
const POINTS_CAP  = 6

const TEXT_MIME  = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]
const IMAGE_MIME = ['image/png', 'image/jpeg']

const CONFIDENCE_COLOR = { High: '#34d399', Medium: '#fbbf24', Low: '#f87171' }
const CONFIDENCE_BG    = { High: 'rgba(52,211,153,0.12)', Medium: 'rgba(251,191,36,0.12)', Low: 'rgba(248,113,113,0.12)' }

const SEVERITY = {
  critical: { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',  label: 'Critical' },
  moderate: { color: '#D97706', bg: 'rgba(217,119,6,0.12)',  label: 'Moderate' },
  low:      { color: '#059669', bg: 'rgba(5,150,105,0.12)',  label: 'Low Risk' },
}

const isImageFile = (f) => IMAGE_MIME.includes(f?.type) || /\.(png|jpe?g)$/i.test(f?.name ?? '')
const isTextFile  = (f) => TEXT_MIME.includes(f?.type)  || /\.(pdf|docx|txt)$/i.test(f?.name ?? '')

function formatBytes(bytes) {
  if (bytes < 1024)         return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getRiskSeverity(text) {
  const s = text.toLowerCase()
  if (/\b(critical|high|serious|urgent|severe|imminent|immediately|arrest|criminal|illegal|court order)\b/.test(s)) return 'critical'
  if (/\b(moderate|medium|significant|important|caution|warning|potential|risk|deadline|expir)\b/.test(s)) return 'moderate'
  return 'low'
}

// ── Panel helpers ──────────────────────────────────────────────────────────────

function panelStyle(isDark) {
  return {
    borderRadius: 16,
    background:   isDark ? 'rgba(255,255,255,0.03)' : '#FFFFFF',
    border:       isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(15,23,42,0.08)',
    boxShadow:    isDark
      ? '0 1px 4px rgba(0,0,0,0.28)'
      : '0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.03)',
  }
}

function sepStyle(isDark) {
  return { borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(15,23,42,0.06)' }
}

function PanelHeader({ icon: Icon, color, bg, label, isDark }) {
  return (
    <div className="flex items-center gap-2.5 px-5 py-3" style={sepStyle(isDark)}>
      <div
        className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
        style={{ background: bg, border: `1px solid ${color}25` }}
      >
        <Icon size={12} style={{ color }} />
      </div>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.07em', textTransform: 'uppercase', fontWeight: 600 }}>
        {label}
      </span>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function ExpandableSummary({ text, rtl }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div>
      <p
        className="text-sm leading-relaxed"
        style={{
          color: 'var(--text-secondary)',
          overflow: 'hidden',
          display: '-webkit-box',
          WebkitLineClamp: expanded ? 'unset' : 6,
          WebkitBoxOrient: 'vertical',
        }}
        dir="auto"
      >
        {text}
      </p>
      <button
        onClick={() => setExpanded(x => !x)}
        className="flex items-center gap-1 mt-2.5 text-[11px] font-medium transition-colors"
        style={{ color: 'var(--text-muted)' }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-secondary)' }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)' }}
      >
        {expanded ? <><ChevronUp size={11} /> Show less</> : <><ChevronDown size={11} /> Show more</>}
      </button>
    </div>
  )
}

function FindingList({ items, emptyKey, t, rtl, isDark }) {
  const [expanded, setExpanded] = useState(false)
  if (!items || items.length === 0) {
    return <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{t(emptyKey)}</p>
  }
  const visible = expanded ? items : items.slice(0, POINTS_CAP)
  const hidden  = items.length - POINTS_CAP

  return (
    <div>
      {visible.map((item, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: rtl ? 6 : -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04, duration: 0.16 }}
          className="flex items-start gap-3 py-3"
          style={i < visible.length - 1 ? sepStyle(isDark) : {}}
        >
          <span
            className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center font-bold mt-0.5"
            style={{ background: 'rgba(5,150,105,0.14)', color: '#059669', fontSize: 10, minWidth: 20 }}
          >
            {i + 1}
          </span>
          <span className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }} dir="auto">
            {item}
          </span>
        </motion.div>
      ))}
      {hidden > 0 && (
        <button
          onClick={() => setExpanded(x => !x)}
          className="flex items-center gap-1 mt-1 text-[11px] font-medium transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-secondary)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)' }}
        >
          {expanded
            ? <><ChevronUp size={11} /> Show less</>
            : <><ChevronDown size={11} /> {hidden} more finding{hidden !== 1 ? 's' : ''}</>}
        </button>
      )}
    </div>
  )
}

function BulletList({ items, emptyKey, t, rtl }) {
  if (!items || items.length === 0) {
    return <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{t(emptyKey)}</p>
  }
  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: rtl ? 6 : -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04, duration: 0.16 }}
          className="flex items-start gap-2.5 text-sm leading-relaxed"
        >
          <ArrowRight size={13} className="flex-shrink-0 mt-0.5" style={{ color: '#0284C7' }} />
          <span dir="auto" style={{ color: 'var(--text-secondary)' }}>{item}</span>
        </motion.li>
      ))}
    </ul>
  )
}

function RiskList({ items, emptyKey, t, isDark }) {
  if (!items || items.length === 0) {
    return <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{t(emptyKey)}</p>
  }
  return (
    <div>
      {items.map((text, i) => {
        const s = SEVERITY[getRiskSeverity(text)]
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex items-start gap-2.5 py-2.5"
            style={i < items.length - 1 ? sepStyle(isDark) : {}}
          >
            <div className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5" style={{ background: s.color }} />
            <span className="text-xs leading-relaxed flex-1" style={{ color: 'var(--text-secondary)' }} dir="auto">
              {text}
            </span>
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 self-start"
              style={{ background: s.bg, color: s.color }}
            >
              {s.label}
            </span>
          </motion.div>
        )
      })}
    </div>
  )
}

function LawChips({ items, emptyKey, t }) {
  if (!items || items.length === 0) {
    return <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{t(emptyKey)}</p>
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((law, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: i * 0.04 }}
          className="text-[11px] px-2.5 py-1 rounded-lg leading-snug"
          style={{
            background: 'rgba(2,132,199,0.08)',
            border: '1px solid rgba(2,132,199,0.18)',
            color: 'var(--text-secondary)',
          }}
          dir="auto"
          title={law}
        >
          {law.length > 48 ? law.slice(0, 48) + '…' : law}
        </motion.span>
      ))}
    </div>
  )
}

function DeadlineRows({ items, emptyKey, t, rtl, isDark }) {
  if (!items || items.length === 0) {
    return <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>{t(emptyKey)}</p>
  }
  return (
    <div>
      {items.map((text, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: rtl ? 6 : -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className="flex items-start gap-2.5 py-2.5"
          style={i < items.length - 1 ? sepStyle(isDark) : {}}
        >
          <Clock size={11} className="flex-shrink-0 mt-0.5" style={{ color: '#D97706' }} />
          <span className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }} dir="auto">
            {text}
          </span>
        </motion.div>
      ))}
    </div>
  )
}

function SourcePreview({ file, imagePreviewUrl, isExtracting, extractError, extractedText, previewText, isTruncated, charCount, t }) {
  if (isImageFile(file)) {
    return (
      <Card padding="p-5">
        <div className="label mb-3">{t('doc_image_preview')}</div>
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
      </Card>
    )
  }
  if (isExtracting) {
    return (
      <Card padding="p-5">
        <div className="flex items-center gap-3 py-6 justify-center" style={{ color: 'var(--text-muted)' }}>
          <Spinner size={18} />
          <span className="text-sm">{t('doc_extracting')}</span>
        </div>
      </Card>
    )
  }
  if (extractError) {
    return (
      <Alert type="warning">
        <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
        <span>{extractError}</span>
      </Alert>
    )
  }
  if (extractedText !== null && extractedText === '') {
    return (
      <Alert type="warning">
        <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
        <span>{t('doc_no_text')}</span>
      </Alert>
    )
  }
  if (extractedText) {
    return (
      <Card padding="p-5">
        <div className="label mb-3">{t('doc_preview_label')}</div>
        <div className="flex items-center justify-between mb-2 text-xs" style={{ color: 'var(--text-muted)' }} dir="ltr">
          <span>{charCount.toLocaleString()} {t('doc_preview_chars')}</span>
          {isTruncated && <span className="italic">{t('doc_preview_truncated')}</span>}
        </div>
        <div
          className="rounded-xl p-3 text-xs leading-relaxed overflow-y-auto"
          style={{
            maxHeight: 220,
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
      </Card>
    )
  }
  return null
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function DocumentAnalysisPage() {
  const t = useT()
  const { language, theme } = useAppStore()
  const rtl    = isRTL(language)
  const isDark = theme === 'dark'

  const [file,            setFile]            = useState(null)
  const [isDragging,      setIsDragging]      = useState(false)
  const [validationError, setValidationError] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [isExtracting,    setIsExtracting]    = useState(false)
  const [extractedText,   setExtractedText]   = useState(null)
  const [extractError,    setExtractError]    = useState('')

  const [isAnalyzing,   setIsAnalyzing]   = useState(false)
  const [analysis,      setAnalysis]      = useState(null)
  const [analysisError, setAnalysisError] = useState('')

  const [activeTab, setActiveTab] = useState('analysis')

  const fileInputRef = useRef(null)

  useEffect(
    () => () => { if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl) },
    [imagePreviewUrl],
  )

  const processFile = useCallback(async (f) => {
    setValidationError('')
    setFile(null)
    setImagePreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return '' })
    setExtractedText(null)
    setExtractError('')
    setIsExtracting(false)
    setAnalysis(null)
    setAnalysisError('')
    setActiveTab('analysis')

    if (!isImageFile(f) && !isTextFile(f)) { setValidationError(t('doc_validation_type')); return }
    if (f.size > MAX_BYTES)                { setValidationError(t('doc_validation_size'));  return }

    setFile(f)
    if (isImageFile(f)) { setImagePreviewUrl(URL.createObjectURL(f)); return }

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
    setAnalysis(null); setAnalysisError(''); setActiveTab('analysis')
  }

  const analyzeDocument = useCallback(async () => {
    if (!file || isAnalyzing) return
    setIsAnalyzing(true)
    setAnalysisError('')
    setAnalysis(null)
    setActiveTab('analysis')

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

  const previewText = (extractedText || '').slice(0, PREVIEW_CAP)
  const isTruncated = (extractedText?.length ?? 0) > PREVIEW_CAP
  const charCount   =  extractedText?.length ?? 0
  const la          = analysis?.legal_analysis
  const canAnalyze  = file && !isExtracting && !isAnalyzing

  const sourcePreviewProps = { file, imagePreviewUrl, isExtracting, extractError, extractedText, previewText, isTruncated, charCount, t }

  // Shared panel style tokens
  const ps = panelStyle(isDark)

  return (
    <div className="max-w-5xl mx-auto px-4 py-6" dir={rtl ? 'rtl' : 'ltr'}>
      <SectionHeader
        eyebrow={t('doc_eyebrow')}
        title={t('doc_title')}
        description={t('doc_sub')}
      />

      <AnimatePresence mode="wait">
        {!file ? (
          /* ── Empty state ─────────────────────────────────────────────────── */
          <motion.div
            key="empty"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="max-w-lg mx-auto mb-8">
              <div
                onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className="rounded-2xl transition-all duration-200 text-center cursor-pointer"
                style={{
                  border: isDragging
                    ? `2px dashed ${isDark ? '#7C3AED' : 'rgba(124,58,237,0.40)'}`
                    : `2px dashed ${isDark ? 'rgba(255,255,255,0.12)' : '#D8DCE8'}`,
                  background: isDragging
                    ? (isDark ? 'rgba(124,58,237,0.06)' : 'rgba(124,58,237,0.03)')
                    : (isDark ? 'rgba(255,255,255,0.02)' : '#FAFBFE'),
                  padding: '2.5rem 1.5rem',
                }}
              >
                <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg" className="hidden" onChange={onInputChange} />
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                  style={{
                    background: isDragging
                      ? (isDark ? 'rgba(124,58,237,0.16)' : 'rgba(124,58,237,0.08)')
                      : (isDark ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.04)'),
                    border: isDark ? '1px solid rgba(255,255,255,0.09)' : '1px solid rgba(15,23,42,0.08)',
                    transition: 'background 0.2s',
                  }}
                >
                  <Upload
                    size={24}
                    style={{
                      color: isDragging
                        ? (isDark ? '#a78bfa' : '#7C3AED')
                        : (isDark ? 'rgba(255,255,255,0.35)' : 'rgba(15,23,42,0.38)'),
                      transition: 'color 0.2s',
                    }}
                  />
                </div>
                <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>{t('doc_upload_hint')}</p>
                <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>{t('doc_supported_files')}</p>
                <div className="flex items-center justify-center gap-2 mb-5">
                  {['PDF', 'DOCX', 'TXT', 'PNG', 'JPG'].map(ext => (
                    <span key={ext} className="px-2 py-0.5 rounded text-[10px] font-mono" style={{
                      background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.04)',
                      border: isDark ? '1px solid rgba(255,255,255,0.09)' : '1px solid rgba(15,23,42,0.09)',
                      color: 'var(--text-muted)',
                    }}>{ext}</span>
                  ))}
                </div>
                <button type="button" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }} className="btn-primary py-2">
                  {t('doc_upload_label')}
                </button>
              </div>
              <AnimatePresence>
                {validationError && (
                  <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="mt-3">
                    <Alert type="danger"><AlertCircle size={15} className="flex-shrink-0 mt-0.5" /><span>{validationError}</span></Alert>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* What you'll get */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { Icon: FileText, color: '#6366F1', bg: 'rgba(99,102,241,0.10)',
                  title: language === 'Urdu' ? 'قانونی خلاصہ' : 'Legal Summary',
                  desc:  language === 'Urdu' ? 'اہم نتائج اور دستاویز کی درجہ بندی' : 'Key findings and document type classification' },
                { Icon: Shield,   color: '#EF4444', bg: 'rgba(239,68,68,0.10)',
                  title: language === 'Urdu' ? 'خطرے کا جائزہ' : 'Risk Assessment',
                  desc:  language === 'Urdu' ? 'خطرات، آخری تاریخیں اور فوری نشانات' : 'Identified risks, deadlines and urgent flags' },
                { Icon: BookOpen, color: '#0284C7', bg: 'rgba(2,132,199,0.10)',
                  title: language === 'Urdu' ? 'قانونی حوالہ جات' : 'Law Citations',
                  desc:  language === 'Urdu' ? 'قانونی دفعات اور طریقہ کار' : 'Referenced statutes and procedural guidance' },
              ].map(({ Icon, color, bg, title, desc }, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.07 }}
                  className="card p-4 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: bg, border: `1px solid ${color}28` }}>
                    <Icon size={15} style={{ color }} />
                  </div>
                  <div>
                    <p className="text-xs font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>{title}</p>
                    <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-muted)' }}>{desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

        ) : (
          /* ── File loaded state ───────────────────────────────────────────── */
          <motion.div key="file-loaded" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-5">

            {/* ── Top bar ──────────────────────────────────────────────────── */}
            <div
              className="flex items-center gap-3 px-4 py-3 rounded-2xl"
              style={ps}
            >
              {/* File icon */}
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{
                  background: isImageFile(file) ? 'rgba(52,211,153,0.10)' : 'rgba(99,102,241,0.10)',
                  border:     isImageFile(file) ? '1px solid rgba(52,211,153,0.20)' : '1px solid rgba(99,102,241,0.20)',
                }}
              >
                {isImageFile(file)
                  ? <Image    size={16} style={{ color: '#34d399' }} />
                  : <FileText size={16} style={{ color: '#818cf8' }} />}
              </div>

              {/* Name + status */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }} dir="ltr">
                  {file.name}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{formatBytes(file.size)}</span>
                  {isExtracting && (
                    <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      <Spinner size={10} /> {t('doc_extracting')}
                    </span>
                  )}
                  {!isExtracting && extractError && (
                    <span className="text-[11px]" style={{ color: '#f87171' }}>⚠ {t('doc_extract_error')}</span>
                  )}
                  {!isExtracting && !extractError && (extractedText !== null || isImageFile(file)) && !analysis && (
                    <span className="flex items-center gap-1 text-[11px]" style={{ color: '#34d399' }}>
                      <CheckCircle size={10} /> {language === 'Urdu' ? 'تیار' : 'Ready'}
                    </span>
                  )}
                  {analysis && !isAnalyzing && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded-md"
                      style={{ background: 'rgba(52,211,153,0.10)', color: '#34d399', border: '1px solid rgba(52,211,153,0.20)' }}>
                      {language === 'Urdu' ? 'تجزیہ مکمل' : 'Analyzed'}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {isAnalyzing ? (
                  <div className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl" style={{ color: 'var(--text-muted)' }}>
                    <Spinner size={12} /> {t('doc_analyzing')}
                  </div>
                ) : (
                  <button type="button" onClick={analyzeDocument} disabled={!canAnalyze} className="btn-primary py-1.5 text-xs">
                    <Scale size={13} /> {analysis ? t('doc_reanalyze_btn') : t('doc_analyze_btn')}
                  </button>
                )}
                <button
                  type="button" onClick={clearFile}
                  className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
                  style={{ color: 'var(--text-muted)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(15,23,42,0.10)', background: 'transparent' }}
                  onMouseEnter={e => { e.currentTarget.style.color = '#f87171'; e.currentTarget.style.borderColor = 'rgba(248,113,113,0.30)'; e.currentTarget.style.background = 'rgba(248,113,113,0.07)' }}
                  onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.10)'; e.currentTarget.style.background = 'transparent' }}
                >
                  <X size={13} />
                </button>
              </div>
            </div>

            {/* Errors */}
            <AnimatePresence>
              {validationError && (
                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                  <Alert type="danger"><AlertCircle size={15} className="flex-shrink-0 mt-0.5" /><span>{validationError}</span></Alert>
                </motion.div>
              )}
            </AnimatePresence>
            <AnimatePresence>
              {analysisError && (
                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                  <Alert type="danger"><AlertCircle size={14} className="flex-shrink-0 mt-0.5" /><span>{analysisError}</span></Alert>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Pre-analysis: source / image preview */}
            {!analysis && !isAnalyzing && <SourcePreview {...sourcePreviewProps} />}

            {/* Analyzing */}
            {isAnalyzing && (
              <div className="py-16 flex flex-col items-center gap-3">
                <Spinner size={28} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('doc_analyzing')}</p>
              </div>
            )}

            {/* ── Analysis dashboard ───────────────────────────────────────── */}
            <AnimatePresence>
              {analysis && !isAnalyzing && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

                  {/* Tab row */}
                  <div className="flex items-center justify-between">
                    <div
                      className="flex items-center gap-1 p-1 rounded-xl"
                      style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(15,23,42,0.04)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(15,23,42,0.08)', width: 'fit-content' }}
                    >
                      {[
                        { key: 'analysis', label: language === 'Urdu' ? 'تجزیہ' : 'Analysis' },
                        { key: 'source',   label: isImageFile(file) ? (language === 'Urdu' ? 'OCR آؤٹ پٹ' : 'OCR Output') : (language === 'Urdu' ? 'ماخذ متن' : 'Source Text') },
                      ].map(tab => (
                        <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                          className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all"
                          style={activeTab === tab.key
                            ? { background: isDark ? 'rgba(255,255,255,0.09)' : 'rgba(15,23,42,0.07)', color: 'var(--text-primary)' }
                            : { color: 'var(--text-muted)', background: 'transparent' }}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    {/* Meta chips */}
                    <div className="flex items-center gap-1.5 flex-wrap justify-end">
                      {analysis.document_type && analysis.document_type !== 'Unknown' && (
                        <span className="text-[11px] px-2.5 py-1 rounded-full font-medium"
                          style={{ background: 'rgba(99,102,241,0.10)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.20)' }}>
                          {analysis.document_type}
                        </span>
                      )}
                      {la?.confidence && (
                        <span className="text-[11px] px-2.5 py-1 rounded-full font-medium"
                          style={{ background: CONFIDENCE_BG[la.confidence] ?? CONFIDENCE_BG.Medium, color: CONFIDENCE_COLOR[la.confidence] ?? CONFIDENCE_COLOR.Medium, border: `1px solid ${CONFIDENCE_COLOR[la.confidence] ?? CONFIDENCE_COLOR.Medium}35` }}>
                          {la.confidence} Confidence
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Source tab */}
                  {activeTab === 'source' && <SourcePreview {...sourcePreviewProps} />}

                  {/* Analysis tab */}
                  {activeTab === 'analysis' && (
                    <>
                      {/* Edge cases */}
                      {analysis.legal_analysis === null && (
                        <Alert type="info">
                          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                          <span>{language === 'Urdu' ? 'متن نکالا گیا لیکن یہ تجزیہ کے لیے کافی نہیں ہے۔' : 'Text was extracted but was too short for AI analysis. Try a more complete document.'}</span>
                        </Alert>
                      )}
                      {la?.error && (
                        <Alert type="warning">
                          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                          <span>{la.error}</span>
                        </Alert>
                      )}

                      {/* Dashboard grid */}
                      {la && !la.error && (
                        <div className="grid gap-5 lg:grid-cols-[70fr_30fr]">

                          {/* ── LEFT COLUMN ─────────────────────────────────── */}
                          <div className="space-y-5">

                            {/* Executive Summary */}
                            {la.summary && (
                              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
                                <div style={ps}>
                                  <PanelHeader
                                    icon={FileText} color="#6366F1" bg="rgba(99,102,241,0.10)"
                                    label={language === 'Urdu' ? 'قانونی خلاصہ' : t('doc_summary_title')}
                                    isDark={isDark}
                                  />
                                  <div className="px-5 pt-4 pb-5">
                                    <ExpandableSummary text={la.summary} rtl={rtl} />
                                  </div>
                                </div>
                              </motion.div>
                            )}

                            {/* Key Legal Points */}
                            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.10 }}>
                              <div style={ps}>
                                <PanelHeader
                                  icon={Scale} color="#059669" bg="rgba(5,150,105,0.10)"
                                  label={language === 'Urdu' ? 'اہم قانونی نکات' : t('doc_key_points_title')}
                                  isDark={isDark}
                                />
                                <div className="px-5 pt-3 pb-5">
                                  <FindingList items={la.key_legal_points} emptyKey="doc_none_found" t={t} rtl={rtl} isDark={isDark} />
                                </div>
                              </div>
                            </motion.div>

                            {/* Procedural Guidance */}
                            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}>
                              <div style={ps}>
                                <PanelHeader
                                  icon={ArrowRight} color="#0284C7" bg="rgba(2,132,199,0.10)"
                                  label={language === 'Urdu' ? 'طریقہ کار' : t('doc_procedural_title')}
                                  isDark={isDark}
                                />
                                <div className="px-5 pt-4 pb-5">
                                  <BulletList items={la.procedural_guidance} emptyKey="doc_none_found" t={t} rtl={rtl} />
                                </div>
                              </div>
                            </motion.div>

                            {/* Urdu Explanation — Urdu mode only */}
                            {language === 'Urdu' && la.urdu_explanation && (
                              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}>
                                <div style={ps}>
                                  <PanelHeader
                                    icon={Globe} color="#D97706" bg="rgba(217,119,6,0.10)"
                                    label={t('doc_urdu_title')} isDark={isDark}
                                  />
                                  <div className="px-5 pt-4 pb-5">
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)', lineHeight: 1.9, direction: 'rtl', textAlign: 'right' }}>
                                      {la.urdu_explanation}
                                    </p>
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </div>

                          {/* ── RIGHT COLUMN — sticky ──────────────────────── */}
                          <div className="space-y-4 lg:sticky lg:top-[68px] lg:self-start">

                            {/* Document Details */}
                            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
                              <div style={ps}>
                                <PanelHeader
                                  icon={FileText} color="#64748B" bg="rgba(100,116,139,0.10)"
                                  label={language === 'Urdu' ? 'دستاویز کی تفصیلات' : 'Document Details'}
                                  isDark={isDark}
                                />
                                <div className="px-4 py-3 space-y-2">
                                  {[
                                    { key: language === 'Urdu' ? 'فائل' : 'File',       val: file.name },
                                    { key: language === 'Urdu' ? 'سائز' : 'Size',       val: formatBytes(file.size) },
                                    ...(analysis.document_type && analysis.document_type !== 'Unknown'
                                      ? [{ key: language === 'Urdu' ? 'قسم' : 'Type',  val: analysis.document_type }] : []),
                                    ...(la.confidence
                                      ? [{ key: language === 'Urdu' ? 'اعتماد' : 'Confidence', val: la.confidence, color: CONFIDENCE_COLOR[la.confidence] }] : []),
                                    ...(analysis.detected_language
                                      ? [{ key: language === 'Urdu' ? 'زبان' : 'Language', val: analysis.detected_language }] : []),
                                  ].map(({ key, val, color }) => (
                                    <div key={key} className="flex items-start justify-between gap-2">
                                      <span className="text-[11px] flex-shrink-0" style={{ color: 'var(--text-muted)' }}>{key}</span>
                                      <span className="text-[11px] font-medium text-right truncate max-w-[58%]"
                                        style={{ color: color || 'var(--text-secondary)' }} dir="ltr" title={val}>{val}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </motion.div>

                            {/* Deadlines */}
                            {la.deadlines?.length > 0 && (
                              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.10 }}>
                                <div style={ps}>
                                  <PanelHeader
                                    icon={Clock} color="#D97706" bg="rgba(217,119,6,0.10)"
                                    label={language === 'Urdu' ? 'اہم تاریخیں' : t('doc_deadlines_title')}
                                    isDark={isDark}
                                  />
                                  <div className="px-4 py-3">
                                    <DeadlineRows items={la.deadlines} emptyKey="doc_none_found" t={t} rtl={rtl} isDark={isDark} />
                                  </div>
                                </div>
                              </motion.div>
                            )}

                            {/* Risk Indicators */}
                            {la.risk_indicators?.length > 0 && (
                              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.13 }}>
                                <div style={ps}>
                                  <PanelHeader
                                    icon={Shield} color="#EF4444" bg="rgba(239,68,68,0.10)"
                                    label={language === 'Urdu' ? 'خطرے کے اشارے' : t('doc_risk_title')}
                                    isDark={isDark}
                                  />
                                  <div className="px-4 py-3">
                                    <RiskList items={la.risk_indicators} emptyKey="doc_none_found" t={t} isDark={isDark} />
                                  </div>
                                </div>
                              </motion.div>
                            )}

                            {/* Referenced Laws */}
                            {la.cited_laws?.length > 0 && (
                              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }}>
                                <div style={ps}>
                                  <PanelHeader
                                    icon={BookOpen} color="#0284C7" bg="rgba(2,132,199,0.10)"
                                    label={language === 'Urdu' ? 'قانونی حوالہ جات' : t('doc_laws_title')}
                                    isDark={isDark}
                                  />
                                  <div className="px-4 py-3">
                                    <LawChips items={la.cited_laws} emptyKey="doc_none_found" t={t} />
                                  </div>
                                </div>
                              </motion.div>
                            )}

                            {/* Disclaimer */}
                            <p className="text-[10px] text-center px-2" style={{ color: 'var(--text-muted)', lineHeight: 1.6 }} dir="auto">
                              {la.disclaimer || t('doc_disclaimer')}
                            </p>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Pre-analysis hint */}
            {!analysis && !isAnalyzing && !analysisError && (
              <p className="text-[11px] text-center py-1" style={{ color: 'var(--text-muted)' }}>
                {t('doc_disclaimer')}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

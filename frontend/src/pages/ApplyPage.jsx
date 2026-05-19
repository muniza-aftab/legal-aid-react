import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useT, isRTL, translateCategory } from '@/services/i18n'
import { useAppStore } from '@/services/store'
import { submitApplication } from '@/services/api'
import { SectionHeader, Card, Alert, Spinner } from '@/components/ui/index'

const schema = z.object({
  full_name:   z.string().min(2, 'Name is required'),
  cnic:        z.string().optional(),
  phone:       z.string().min(7, 'Phone number is required'),
  email:       z.string().email('Invalid email').optional().or(z.literal('')),
  city:        z.string().min(1, 'City is required'),
  case_type:   z.string().min(1, 'Case type is required'),
  urgency:     z.string().min(1, 'Urgency is required'),
  description: z.string().min(30, 'Please provide at least 30 characters'),
})

// Must exactly match backend LEGAL_CASE_TYPES from utils/legal_taxonomy.py
const CASE_TYPES = [
  'Family Law', 'Criminal Law', 'Labour Law', 'Property Law',
  'Inheritance Law', 'Cybercrime', 'Harassment', 'Civil Law / Procedure',
  'Contract Law', 'Consumer Rights', 'Constitutional Law', 'General / Other',
]
const URGENCY = ['Low', 'Medium', 'High', 'Critical']
const CITIES  = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Peshawar', 'Quetta', 'Multan', 'Faisalabad', 'Other']

export default function ApplyPage() {
  const t = useT()
  const { language } = useAppStore()
  const rtl = isRTL(language)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(null)
  const [serverError, setServerError] = useState('')

  const { register, handleSubmit, watch, formState: { errors }, reset } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { urgency: '' },
  })

  const selectedUrgency = watch('urgency')

  const onSubmit = async (data) => {
    setLoading(true)
    setServerError('')
    try {
      const result = await submitApplication({ ...data, language })
      setSubmitted(result)
      reset()
    } catch (err) {
      // FastAPI can return detail as a string (our ValueError) or an array
      // of objects (Pydantic 422 validation errors) — handle both
      const detail = err.response?.data?.detail
      const message =
        typeof detail === 'string'  ? detail :
        Array.isArray(detail)       ? detail.map(d => d.msg ?? d).join(' · ') :
        `Submission failed (${err.response?.status ?? 'network error'}). Please try again.`
      setServerError(message)
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
          <CheckCircle size={64} className="mx-auto mb-4" style={{ color: '#34D399' }} />
          <h2 className="font-display text-2xl font-semibold mb-2">{t('apply_success_title')}</h2>
          <p className="mb-4" style={{ color: 'var(--text-muted)' }}>
            {t('apply_success_body')}
          </p>
          {submitted.app_id && (
            <p className="font-mono text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
              {t('apply_ref_id')} <strong>{submitted.app_id}</strong>
            </p>
          )}
          <button onClick={() => setSubmitted(null)} className="btn-primary px-6 py-2">
            {t('apply_again_btn')}
          </button>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6" dir={rtl ? 'rtl' : 'ltr'}>
      <SectionHeader
        eyebrow={t('apply_eyebrow')}
        title={t('apply_title')}
        description={t('apply_sub')}
      />

      <Alert type="info" className="mb-6">
        ℹ️ {t('apply_info')}
      </Alert>

      <Card padding="p-6">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Name */}
            <div>
              <label className="label">{t('form_name')} *</label>
              <input {...register('full_name')} className="input" placeholder={t('form_ph_name')} />
              {errors.full_name && <FieldError msg={errors.full_name.message} />}
            </div>

            {/* CNIC */}
            <div>
              <label className="label">{t('form_cnic')}</label>
              <input {...register('cnic')} className="input" placeholder={t('form_ph_cnic')} />
            </div>

            {/* Phone */}
            <div>
              <label className="label">{t('form_phone')} *</label>
              <input {...register('phone')} className="input" placeholder={t('form_ph_phone')} />
              {errors.phone && <FieldError msg={errors.phone.message} />}
            </div>

            {/* Email */}
            <div>
              <label className="label">{t('form_email')}</label>
              <input {...register('email')} className="input" placeholder={t('form_ph_email')} type="email" />
              {errors.email && <FieldError msg={errors.email.message} />}
            </div>

            {/* City */}
            <div>
              <label className="label">{t('form_city')} *</label>
              <select {...register('city')} className="input">
                <option value="">{t('form_select_city')}</option>
                {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              {errors.city && <FieldError msg={errors.city.message} />}
            </div>

            {/* Case Type */}
            <div>
              <label className="label">{t('form_casetype')} *</label>
              <select {...register('case_type')} className="input">
                <option value="">{t('form_select_type')}</option>
                {CASE_TYPES.map(c => <option key={c} value={c}>{translateCategory(c, language)}</option>)}
              </select>
              {errors.case_type && <FieldError msg={errors.case_type.message} />}
            </div>
          </div>

          {/* Urgency */}
          <div>
            <label className="label">{t('form_urgency')} *</label>
            <div className="flex gap-2 flex-wrap mt-1">
              {URGENCY.map(u => {
                const active = selectedUrgency === u
                return (
                  <label key={u} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <input
                      type="radio"
                      value={u}
                      {...register('urgency')}
                      className="sr-only"
                    />
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        height: 32,
                        padding: '0 14px',
                        borderRadius: 8,
                        fontSize: 13,
                        fontWeight: 500,
                        whiteSpace: 'nowrap',
                        lineHeight: 1,
                        transition: 'background 0.14s, border-color 0.14s, color 0.14s',
                        border: active
                          ? '1.5px solid rgba(124,58,237,0.55)'
                          : '1.5px solid var(--border-muted)',
                        background: active ? 'rgba(124,58,237,0.12)' : 'transparent',
                        color: active ? '#a78bfa' : 'var(--text-secondary)',
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          flexShrink: 0,
                          background: active ? '#7C3AED' : 'var(--text-muted)',
                          transition: 'background 0.14s',
                        }}
                      />
                      {t('urgency_' + u.toLowerCase())}
                    </span>
                  </label>
                )
              })}
            </div>
            {errors.urgency && <FieldError msg={errors.urgency.message} />}
          </div>

          {/* Description */}
          <div>
            <label className="label">{t('form_desc')} *</label>
            <textarea
              {...register('description')}
              rows={5}
              className="input resize-none"
              placeholder={t('form_ph_desc')}
              dir={rtl ? 'rtl' : 'ltr'}
            />
            {errors.description && <FieldError msg={errors.description.message} />}
          </div>

          {serverError && <Alert type="danger">⚠️ {serverError}</Alert>}

          <button type="submit" disabled={loading} className="btn-primary w-full py-3 justify-center">
            {loading ? <Spinner size={18} /> : null}
            {loading ? t('submitting_btn') : t('submit_btn')}
          </button>
        </form>
      </Card>
    </div>
  )
}

function FieldError({ msg }) {
  return <p className="mt-1 text-xs" style={{ color: 'var(--danger-text)' }}>{msg}</p>
}

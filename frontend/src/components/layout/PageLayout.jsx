import { useAppStore } from '@/services/store'
import { isRTL } from '@/services/i18n'

const WIDTHS = {
  narrow:   'max-w-2xl',
  compact:  'max-w-3xl',
  standard: 'max-w-4xl',
  medium:   'max-w-5xl',
  wide:     'max-w-6xl',
  full:     'max-w-7xl',
}

export function PageContainer({ children, size = 'standard', align = 'left', dir: dirProp, className = '' }) {
  const language = useAppStore(s => s.language)
  const rtl = isRTL(language)
  const dir = dirProp ?? (rtl ? 'rtl' : 'ltr')
  const alignClass = align === 'center' ? 'mx-auto' : ''
  return (
    <div
      className={`w-full ${WIDTHS[size] ?? WIDTHS.standard} ${alignClass} px-5 md:px-8 lg:px-12 pt-10 pb-12 ${className}`}
      dir={dir}
    >
      {children}
    </div>
  )
}

export function TwoColumn({ children, ratio = '65/35', gap = 'default', className = '' }) {
  const gridClass = {
    '65/35': 'lg:grid-cols-[65fr_35fr]',
    '70/30': 'lg:grid-cols-[70fr_30fr]',
    '1/1':   'md:grid-cols-2',
  }[ratio] ?? 'lg:grid-cols-[65fr_35fr]'
  const gapClass = { tight: 'gap-4 lg:gap-5', default: 'gap-5 lg:gap-6', loose: 'gap-6 lg:gap-8' }[gap] ?? 'gap-5 lg:gap-6'
  return (
    <div className={`grid grid-cols-1 ${gridClass} ${gapClass} ${className}`}>
      {children}
    </div>
  )
}

export function PageSection({ children, gap = 'default', className = '' }) {
  const gapClass = {
    tight:   'space-y-4',
    default: 'space-y-6',
    loose:   'space-y-8',
    wide:    'space-y-10',
  }[gap] ?? 'space-y-6'
  return <div className={`${gapClass} ${className}`}>{children}</div>
}

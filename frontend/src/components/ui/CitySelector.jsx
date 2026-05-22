import { useAppStore } from '@/services/store'

const CITIES = ['Any City','Karachi','Lahore','Islamabad','Rawalpindi','Peshawar','Quetta','Multan','Faisalabad']

const CITIES_URDU = {
  'Any City':    'کوئی بھی شہر',
  'Karachi':     'کراچی',
  'Lahore':      'لاہور',
  'Islamabad':   'اسلام آباد',
  'Rawalpindi':  'راولپنڈی',
  'Peshawar':    'پشاور',
  'Quetta':      'کوئٹہ',
  'Multan':      'ملتان',
  'Faisalabad':  'فیصل آباد',
}

const LANGUAGES = ['English','Urdu']

function compactStyle(isDark, isUrdu) {
  return {
    ...(isDark ? {
      color: 'rgba(255,255,255,0.55)',
      borderColor: 'rgba(255,255,255,0.12)',
      background: 'rgba(255,255,255,0.05)',
    } : {
      color: 'rgba(15,23,42,0.65)',
      borderColor: 'rgba(15,23,42,0.12)',
      background: '#FFFFFF',
    }),
    borderRadius: 10,
    ...(isUrdu && {
      fontFamily: 'var(--font-urdu)',
      textAlign: 'right',
      direction: 'rtl',
    }),
  }
}

export default function CitySelector({ compact }) {
  const { city, setCity, theme, language } = useAppStore()
  const isUrdu = language === 'Urdu'
  return (
    <div>
      {!compact && <div className="label">City</div>}
      <select
        value={city || 'Any City'}
        onChange={e => setCity(e.target.value === 'Any City' ? '' : e.target.value)}
        className={compact
          ? 'w-full text-xs px-2 py-1.5 border outline-none transition-colors'
          : 'input text-sm'}
        style={compact ? compactStyle(theme === 'dark', isUrdu) : {}}
      >
        {CITIES.map(c => (
          <option key={c} value={c}>
            {isUrdu ? CITIES_URDU[c] : c}
          </option>
        ))}
      </select>
    </div>
  )
}

export function LanguageSelector({ compact }) {
  const { language, setLanguage, theme } = useAppStore()
  const isUrdu = language === 'Urdu'
  return (
    <div>
      {!compact && <div className="label">Language</div>}
      <select
        value={language}
        onChange={e => setLanguage(e.target.value)}
        className={compact
          ? 'w-full text-xs px-2 py-1.5 border outline-none transition-colors'
          : 'input text-sm'}
        style={compact ? compactStyle(theme === 'dark', isUrdu) : {}}
      >
        {LANGUAGES.map(l => (
          <option key={l} value={l}>{l === 'Urdu' ? 'اردو' : 'English'}</option>
        ))}
      </select>
    </div>
  )
}

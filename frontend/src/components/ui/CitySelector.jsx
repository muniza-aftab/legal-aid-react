import { useAppStore } from '@/services/store'

const CITIES = ['Any City','Karachi','Lahore','Islamabad','Rawalpindi','Peshawar','Quetta','Multan','Faisalabad']
const LANGUAGES = ['English','Urdu']

const compactStyle = {
  color: 'rgba(255,255,255,0.55)',
  borderColor: 'rgba(255,255,255,0.12)',
  background: 'rgba(255,255,255,0.05)',
  borderRadius: 10,
}

export default function CitySelector({ compact }) {
  const { city, setCity } = useAppStore()
  return (
    <div>
      {!compact && <div className="label">City</div>}
      <select
        value={city || 'Any City'}
        onChange={e => setCity(e.target.value === 'Any City' ? '' : e.target.value)}
        className={compact
          ? 'w-full text-xs px-2 py-1.5 border outline-none transition-colors'
          : 'input text-sm'}
        style={compact ? compactStyle : {}}
      >
        {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
    </div>
  )
}

export function LanguageSelector({ compact }) {
  const { language, setLanguage } = useAppStore()
  return (
    <div>
      {!compact && <div className="label">Language</div>}
      <select
        value={language}
        onChange={e => setLanguage(e.target.value)}
        className={compact
          ? 'w-full text-xs px-2 py-1.5 border outline-none transition-colors'
          : 'input text-sm'}
        style={compact ? compactStyle : {}}
      >
        {LANGUAGES.map(l => (
          <option key={l} value={l}>{l === 'Urdu' ? 'اردو' : 'English'}</option>
        ))}
      </select>
    </div>
  )
}

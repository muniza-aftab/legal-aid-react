export default function ScalesIcon({ size = 70, gid = 'lsM' }) {
  const m  = `url(#${gid})`
  const mD = `url(#${gid}D)`
  const mG = `url(#${gid}G)`
  const pF = `url(#${gid}P)`
  return (
    <svg viewBox="0 0 56 56" width={size} height={size} fill="none" style={{ display: 'block', flexShrink: 0 }}>
      <defs>
        <linearGradient id={gid} x1="28" y1="2" x2="28" y2="54" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#FFFFFF" />
          <stop offset="55%"  stopColor="#E2E8F0" />
          <stop offset="100%" stopColor="#B4C2D6" />
        </linearGradient>
        <linearGradient id={`${gid}D`} x1="28" y1="2" x2="28" y2="54" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#D1DAE8" />
          <stop offset="100%" stopColor="#8FA3BF" />
        </linearGradient>
        <linearGradient id={`${gid}G`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="rgba(255,255,255,0.32)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
        <radialGradient id={`${gid}P`} cx="50%" cy="25%" r="70%">
          <stop offset="0%"   stopColor="rgba(255,255,255,0.16)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0.03)" />
        </radialGradient>
      </defs>

      {/* Mughal arch hint */}
      <path d="M19 51 L19 29 Q19 17 28 17 Q37 17 37 29 L37 51"
            stroke="white" strokeWidth="0.55" fill="none" opacity="0.065" />

      {/* Gem */}
      <circle cx="28" cy="6.8" r="3.6" fill={m} />
      <circle cx="28" cy="6.8" r="2.1" fill="white" opacity="0.22" />
      <ellipse cx="26.8" cy="5.6" rx="1.3" ry="1.0" fill="white" opacity="0.55" />

      {/* Pivot rod */}
      <rect x="27.0" y="10.2" width="2.0" height="4.5" rx="1.0" fill={m} />

      {/* Crossbar */}
      <rect x="5.0" y="14.5" width="46" height="3.2" rx="1.6" fill={m} />
      <rect x="5.0" y="14.5" width="46" height="1.4" rx="0.7" fill={mG} opacity="0.55" />

      {/* End knobs */}
      <circle cx="7.8"  cy="16.1" r="2.8" fill={m} />
      <circle cx="48.2" cy="16.1" r="2.8" fill={m} />
      <ellipse cx="7.0"  cy="15.2" rx="1.2" ry="0.9" fill="white" opacity="0.35" />
      <ellipse cx="47.4" cy="15.2" rx="1.2" ry="0.9" fill="white" opacity="0.35" />

      {/* Left V-chains */}
      <line x1="6.8"  y1="19.0" x2="4.5"  y2="28.2" stroke={m} strokeWidth="1.0" opacity="0.78" />
      <line x1="8.8"  y1="19.0" x2="11.0" y2="28.2" stroke={m} strokeWidth="1.0" opacity="0.78" />

      {/* Right V-chains */}
      <line x1="47.2" y1="19.0" x2="45.0" y2="28.2" stroke={m} strokeWidth="1.0" opacity="0.78" />
      <line x1="49.2" y1="19.0" x2="51.5" y2="28.2" stroke={m} strokeWidth="1.0" opacity="0.78" />

      {/* Left pan */}
      <line x1="1.2" y1="28.2" x2="14.8" y2="28.2" stroke={m}  strokeWidth="2.2" strokeLinecap="round" />
      <path d="M1.2 28.2 Q8 38.0 14.8 28.2" stroke={mD} strokeWidth="1.6" fill={pF} strokeLinecap="round" />
      <path d="M4.0 28.8 Q8.0 34.5 12.0 28.8" stroke="white" strokeWidth="0.7" fill="none" opacity="0.28" />

      {/* Right pan */}
      <line x1="41.2" y1="28.2" x2="54.8" y2="28.2" stroke={m}  strokeWidth="2.2" strokeLinecap="round" />
      <path d="M41.2 28.2 Q48 38.0 54.8 28.2" stroke={mD} strokeWidth="1.6" fill={pF} strokeLinecap="round" />
      <path d="M44.0 28.8 Q48.0 34.5 52.0 28.8" stroke="white" strokeWidth="0.7" fill="none" opacity="0.28" />

      {/* Pillar */}
      <rect x="26.7" y="17.5" width="2.6" height="25.0" rx="1.3" fill={m} />
      <rect x="27.2" y="17.5" width="1.0" height="25.0" rx="0.5" fill="white" opacity="0.18" />

      {/* Base */}
      <rect x="22.5" y="42.5" width="11.0" height="2.8" rx="1.1"  fill={mD} />
      <rect x="18.0" y="45.2" width="20.0" height="3.8" rx="1.9"  fill={m} />
      <rect x="19.5" y="45.5" width="17.0" height="1.2" rx="0.6"  fill="white" opacity="0.20" />
    </svg>
  )
}

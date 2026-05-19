/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['ui-monospace', 'SFMono-Regular', 'monospace'],
        display: ['Inter', 'sans-serif'],
        urdu:    ['Noto Nastaliq Urdu', 'serif'],
      },
      colors: {
        primary: {
          DEFAULT: '#1e3a6e',
          hover:   '#16306b',
          light:   '#2d5aa0',
          50:      '#eef2fb',
          100:     '#d4dff5',
          900:     '#0d1f3d',
        },
        accent: {
          DEFAULT: '#c9a84c',
          hover:   '#b8943f',
          light:   '#e4c97e',
          50:      '#fdf8ed',
        },
        success: {
          DEFAULT: '#1d6b3a',
          bg:      '#f0fdf4',
          border:  '#bbf7d0',
          text:    '#15803d',
        },
        warning: {
          DEFAULT: '#92400e',
          bg:      '#fffbeb',
          border:  '#fde68a',
          text:    '#b45309',
        },
        danger: {
          DEFAULT: '#7f1d1d',
          bg:      '#fef2f2',
          border:  '#fecaca',
          text:    '#dc2626',
        },
        critical: {
          bg:     '#1c0505',
          border: '#7f1d1d',
          text:   '#fca5a5',
        },
        sidebar: '#111827',
        surface: '#ffffff',
        page:    '#f7f8fa',
        subtle:  '#f3f4f6',
      },
      borderRadius: {
        'sm':  '4px',
        'md':  '7px',
        'lg':  '10px',
        'xl':  '14px',
        '2xl': '20px',
      },
      boxShadow: {
        xs:  '0 1px 2px rgba(0,0,0,.05)',
        sm:  '0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)',
        md:  '0 4px 6px -1px rgba(0,0,0,.07)',
        lg:  '0 10px 15px -3px rgba(0,0,0,.08)',
        card:'0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)',
      },
      keyframes: {
        'fade-in': {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '.7' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-in':   'fade-in 0.25s ease-out',
        'slide-in':  'slide-in 0.2s ease-out',
        'pulse-soft':'pulse-soft 2s ease-in-out infinite',
        shimmer:     'shimmer 1.5s infinite',
      },
    },
  },
  plugins: [],
}

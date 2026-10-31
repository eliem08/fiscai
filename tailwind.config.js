/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      sky: {
        DEFAULT: '#0593C6',
        ink: '#047AA5',
        wash: '#E3F3F9',
      },
      pink: {
        DEFAULT: '#D83995',
        ink: '#B82A7C',
        wash: '#FBE8F2',
      },
      paper: '#FCFFFF',
      surface: '#F2F7F9',
      line: '#D7E3E8',
      ink: {
        DEFAULT: '#0A2533',
        2: '#4A6573',
      },
      ok: '#1F7A4D',
      fail: '#B4232C',
    },
    fontFamily: {
      heading: ["'Readex Pro'", 'sans-serif'],
      sans: ["'IBM Plex Sans'", "'IBM Plex Sans Arabic'", 'sans-serif'],
    },
  },
  plugins: [],
};

import type { Config } from "tailwindcss";

/**
 * AVENEL Design System Tailwind Configuration
 * Implements ARCHITECTURE.md Part E specification exactly.
 * No unapproved colors, gradients, blurs, or shadows.
 */
const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    // 4px base spacing grid (0: 0, 1: 4px, 2: 8px, ...)
    spacing: {
      0: "0px",
      0.5: "2px",
      1: "4px",
      1.5: "6px",
      2: "8px",
      2.5: "10px",
      3: "12px",
      3.5: "14px",
      4: "16px",
      5: "20px",
      6: "24px",
      7: "28px",
      8: "32px",
      9: "36px",
      10: "40px",
      11: "44px",
      12: "48px",
      14: "56px",
      16: "64px",
      20: "80px",
      24: "96px",
      28: "112px",
      32: "128px",
      55: "220px", // persistent left rail (220px)
    },
    colors: {
      transparent: "transparent",
      current: "currentColor",
      // Exact Part E.2 tokens
      sky: {
        DEFAULT: "#0593C6",
        ink: "#047AA5",
        wash: "#E3F3F9",
      },
      pink: {
        DEFAULT: "#D83995",
        ink: "#B82A7C",
        wash: "#FBE8F2",
      },
      paper: "#FCFFFF",
      surface: "#F2F7F9",
      line: "#D7E3E8",
      ink: {
        DEFAULT: "#0A2533",
        2: "#4A6573",
      },
      ok: "#1F7A4D",
      fail: "#B4232C",
    },
    fontFamily: {
      heading: ["'Readex Pro'", "sans-serif"],
      sans: ["'IBM Plex Sans'", "'IBM Plex Sans Arabic'", "sans-serif"],
    },
    fontSize: {
      "table-meta": ["0.8125rem", { lineHeight: "1.45" }],
      "table-body": ["0.875rem", { lineHeight: "1.45" }],
      base: ["1rem", { lineHeight: "1.45" }],
      "panel-title": ["1.25rem", { lineHeight: "1.2" }],
      "page-title": ["1.75rem", { lineHeight: "1.2" }],
    },
    borderRadius: {
      none: "0px",
      input: "2px",
      cell: "2px",
      panel: "6px",
      pill: "9999px",
    },
    boxShadow: {
      none: "none",
      floating: "0 8px 24px rgba(10,37,51,0.14)",
    },
    extend: {},
  },
  plugins: [],
};

export default config;

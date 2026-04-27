import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        emet: {
          ink: "#0f172a",
          muted: "#64748b",
          accent: "#2563eb",
          surface: "#f8fafc",
          card: "#ffffff",
        },
        verdict: {
          supported: "#059669",
          partial: "#d97706",
          contradicted: "#dc2626",
          unknown: "#64748b",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;

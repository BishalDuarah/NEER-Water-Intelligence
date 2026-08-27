/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        background: "oklch(19% .032 245 / <alpha-value>)",
        foreground: "oklch(96% .008 230 / <alpha-value>)",
        muted: "oklch(29% .03 246 / <alpha-value>)",
        mutedForeground: "oklch(72% .026 232 / <alpha-value>)",
        primary: "oklch(74% .14 214 / <alpha-value>)",
        primaryForeground: "oklch(18% .04 245 / <alpha-value>)",
        secondary: "oklch(30% .035 246 / <alpha-value>)",
        secondaryForeground: "oklch(95% .01 230 / <alpha-value>)",
        border: "oklch(33% .035 244 / <alpha-value>)",
        input: "oklch(33% .035 244 / <alpha-value>)",
        ring: "oklch(74% .14 214 / <alpha-value>)",
        card: "oklch(23.5% .033 246 / <alpha-value>)",
        ok: "oklch(72% .16 158 / <alpha-value>)",
        warn: "oklch(82% .15 85 / <alpha-value>)",
        destructive: "oklch(62% .21 22 / <alpha-value>)",
        destructiveForeground: "oklch(98% .01 230 / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
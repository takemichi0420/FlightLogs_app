import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d2130",
        mist: "#eef5f8",
        tide: "#0f8ec7",
        sea: "#0f5677",
        shell: "#f7fbfc",
      },
      fontFamily: {
        sans: ["Noto Sans JP", "BIZ UDPGothic", "sans-serif"],
      },
      boxShadow: {
        panel: "0 24px 70px rgba(13, 33, 48, 0.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;

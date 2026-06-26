import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        glow: "0 18px 30px -15px rgba(30, 94, 255, 0.45)",
      },
    },
  },
  plugins: [],
};

export default config;

import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        panel: "#13161b",
        panel2: "#1a1e25",
        line: "#262b34",
        ink: "#e7edf3",
        muted: "#8a93a3",
        accent: "#6ee7b7",
        danger: "#f87171",
        warn: "#fbbf24",
        core: "#60a5fa",
        tech: "#a78bfa",
        em: "#fb923c",
      },
    },
  },
  plugins: [],
};
export default config;

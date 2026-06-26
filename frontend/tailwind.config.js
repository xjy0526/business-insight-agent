/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A",
        muted: "#64748B",
        line: "#E2E8F0",
        canvas: "#F5F7FB",
        navy: "#0B1020",
        aiBlue: "#2563EB",
        aiPurple: "#7C3AED",
      },
      boxShadow: {
        card: "0 12px 28px -16px rgba(15, 23, 42, 0.28)",
        glow: "0 16px 42px -20px rgba(79, 70, 229, 0.7)",
      },
    },
  },
  plugins: [],
};

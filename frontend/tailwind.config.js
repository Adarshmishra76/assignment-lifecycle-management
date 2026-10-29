/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', "system-ui", "sans-serif"],
        serif: ["Newsreader", "Georgia", "serif"],
      },
      colors: {
        // Gradebook palette: blue-black ink, cool paper, green for "checked", red for "marked wrong".
        ink: { 900: "#101B33", 700: "#2B3A5C", 500: "#5B6784", 300: "#A9B1C4" },
        paper: { 50: "#FAFBFC", 100: "#F1F3F6", 200: "#E2E6EC" },
        brand: { 50: "#EEF2FB", 100: "#DDE5F6", 500: "#2F4FA3", 600: "#26418A", 700: "#1D3270" },
        check: { 50: "#E8F5F1", 500: "#14806B", 700: "#0D5C4D" },
        mark: { 50: "#FCEDEE", 500: "#C0303F", 700: "#8F2230" },
        flag: { 50: "#FFF5E0", 500: "#B7791F" },
      },
    },
  },
  plugins: [],
};

/** Palette from the brief. Semantic names (bg, surface, line, fg, muted, accent) switch with the theme. */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        olive: { 900: "#2F3A22", 700: "#4C5A33", 500: "#6F7D45", 300: "#A3B18A", 100: "#DDE3CF" },
        stone: { 950: "#15140F", 800: "#262420", 600: "#4A463F", 400: "#8D877C" },
        cream: { 100: "#F3EFE4", 200: "#E9E3D3", 300: "#D8D0BC" },
        rust: { 700: "#7E2F1C", 500: "#B2432A", 300: "#D8775F" },
        clay: { 700: "#8A4132", 600: "#A14D3B", 300: "#C98B78" },  /* muted brick: the red accent */
        amber: { 400: "#D9A441" },
        ink: "#1B1A17",
        bg: token("bg"),
        surface: token("surface"),
        line: token("line"),
        fg: token("fg"),
        muted: token("muted"),
        accent: token("accent"),
        brick: token("brick"),
        "accent-fg": token("accent-fg"),
        danger: token("danger"),
      },
      fontFamily: {
        serif: ['"Playfair Display"', "Georgia", "serif"],
        sans: ["Inter", '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
      },
    },
  },
};

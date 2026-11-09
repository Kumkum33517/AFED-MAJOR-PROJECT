export type Theme = "light" | "dark";
export const THEME_CHANGED = "afed:theme-changed";

export const currentTheme = (): Theme => (localStorage.getItem("afed_theme") === "dark" ? "dark" : "light");

export function applyTheme(theme: Theme) {
  localStorage.setItem("afed_theme", theme);
  document.documentElement.classList.toggle("dark", theme === "dark");
  window.dispatchEvent(new Event(THEME_CHANGED));
}

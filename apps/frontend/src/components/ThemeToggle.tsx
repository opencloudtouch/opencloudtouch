import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./ThemeToggle.css";

type Theme = "dark" | "light";
const KEY = "oct-theme";

const stored = (): Theme | null => {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
};
const system = (): Theme =>
  window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";

function apply(theme: Theme, animate: boolean) {
  const root = document.documentElement;
  if (animate) {
    root.classList.add("theme-anim");
    window.setTimeout(() => root.classList.remove("theme-anim"), 250);
  }
  root.setAttribute("data-theme", theme);
}

export default function ThemeToggle({ disabled = false }: Readonly<{ disabled?: boolean }>) {
  const { t } = useTranslation();
  // The inline script in index.html set data-theme before the first paint: read it back
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.getAttribute("data-theme") as Theme | null) ?? system()
  );
  const [announce, setAnnounce] = useState("");

  // Until the user has chosen, follow the OS setting live
  useEffect(() => {
    if (stored() || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if (stored()) return;
      const next = mq.matches ? "light" : "dark";
      apply(next, false);
      setTheme(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode: the choice lasts for this session only */
    }
    apply(next, !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
    setTheme(next);
    setAnnounce(t(next === "light" ? "theme.nowLight" : "theme.nowDark"));
  }, [theme, t]);

  // The label names the action; the icon shows what the click switches to
  const label = t(theme === "dark" ? "theme.toLight" : "theme.toDark");

  return (
    <>
      <button
        type="button"
        className="tt"
        onClick={toggle}
        disabled={disabled}
        aria-label={label}
        title={label}
        data-test="theme-toggle"
      >
        <span className="tt-icon" key={theme} aria-hidden="true">
          {theme === "dark" ? Icon.Sun(22) : Icon.Moon(22)}
        </span>
      </button>
      <span className="visually-hidden" role="status">
        {announce}
      </span>
    </>
  );
}

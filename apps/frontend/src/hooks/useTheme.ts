import { useSyncExternalStore } from "react";
import type { ThemeName } from "../pages/aboutUtils";

/** Current theme from <html data-theme>; re-renders when the toggle or the OS listener changes it. */
const subscribe = (onChange: () => void) => {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
};
const snapshot = (): ThemeName =>
  document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";

export const useTheme = (): ThemeName => useSyncExternalStore(subscribe, snapshot, () => "dark");

import { useEffect } from "react";

/** Width of the vertical scrollbar of the scrolling page area (0 for overlay scrollbars or none). */
export function measureScrollbarWidth(): number {
  const main = document.querySelector<HTMLElement>(".app-main");
  return main ? Math.max(0, main.offsetWidth - main.clientWidth) : 0;
}

/**
 * Publishes the scrollbar width of the page area as `--scrollbar-w` on <html>.
 * The page content reserves its scrollbar gutter inside `.app-main`; the header sits outside of it and
 * uses the variable as right padding, so the menu and the page title stay on one line (classic scrollbars).
 */
export function useScrollbarGutter(): void {
  useEffect(() => {
    const root = document.documentElement;
    const apply = () => root.style.setProperty("--scrollbar-w", `${measureScrollbarWidth()}px`);
    apply();
    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(apply);
    };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      root.style.removeProperty("--scrollbar-w");
    };
  }, []);
}

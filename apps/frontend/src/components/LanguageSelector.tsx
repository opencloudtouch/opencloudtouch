import { useRef, useState, useEffect, useCallback, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import "flag-icons/css/flag-icons.min.css";
import { changeLanguage, UI_LOCALES, LOCALE_CONFIGS, UILocale } from "../i18n";
import { Icon } from "./Icon";
import "./LanguageSelector.css";

export default function LanguageSelector() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const currentLocale = (
    UI_LOCALES.includes(i18n.language as UILocale) ? i18n.language : "en"
  ) as UILocale;

  const currentConfig = LOCALE_CONFIGS[currentLocale];

  const close = useCallback(() => setOpen(false), []);

  // Close on outside click
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        close();
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [close]);

  // Close on Escape (and hand focus back to the button if it was inside the list)
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        if (wrapperRef.current?.contains(document.activeElement)) buttonRef.current?.focus();
        close();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [close]);

  // A11y: moving focus into the list when it opens (active option first)
  useEffect(() => {
    if (!open) return;
    const options = wrapperRef.current?.querySelectorAll<HTMLElement>('[role="option"]');
    const active = wrapperRef.current?.querySelector<HTMLElement>(
      '[role="option"][aria-selected="true"]'
    );
    (active ?? options?.[0])?.focus();
  }, [open]);

  const handleSelect = (locale: UILocale) => {
    changeLanguage(locale);
    close();
    buttonRef.current?.focus();
  };

  // A11y: arrow-key navigation inside the listbox
  const moveFocus = (e: KeyboardEvent<HTMLLIElement>) => {
    const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    const options = Array.from(
      wrapperRef.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? []
    );
    const idx = options.indexOf(e.currentTarget);
    const next =
      e.key === "Home"
        ? 0
        : e.key === "End"
          ? options.length - 1
          : (idx + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
    options[next]?.focus();
  };

  return (
    <div className="lang-selector-wrapper" ref={wrapperRef}>
      <button
        ref={buttonRef}
        className="lang-selector"
        aria-label={t("a11y.selectLanguage")}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={`fi fi-${currentConfig.flag} lang-flag`} aria-hidden="true" />
        <span className="lang-code">{currentConfig.shortCode}</span>
      </button>

      {open && (
        <ul className="lang-dropdown" role="listbox" aria-label={t("a11y.selectLanguage")}>
          {UI_LOCALES.map((locale) => {
            const config = LOCALE_CONFIGS[locale];
            const isActive = locale === currentLocale;
            return (
              <li
                key={locale}
                role="option"
                aria-selected={isActive}
                className={`lang-option${isActive ? " lang-option--active" : ""}`}
                tabIndex={0}
                onClick={() => handleSelect(locale)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleSelect(locale);
                  } else {
                    moveFocus(e);
                  }
                }}
              >
                <span className={`fi fi-${config.flag} lang-option-flag`} aria-hidden="true" />
                <span className="lang-option-name">{config.nativeName}</span>
                <span className="lang-option-code">{config.shortCode}</span>
                <span className="lang-option-check" aria-hidden="true">
                  {isActive && Icon.Check(18)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

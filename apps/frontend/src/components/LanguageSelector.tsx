import { useRef, useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import "flag-icons/css/flag-icons.min.css";
import { changeLanguage, UI_LOCALES, LOCALE_CONFIGS, UILocale } from "../i18n";
import "./LanguageSelector.css";

export default function LanguageSelector() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

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

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [close]);

  const handleSelect = (locale: UILocale) => {
    changeLanguage(locale);
    close();
  };

  return (
    <div className="lang-selector-wrapper" ref={wrapperRef}>
      <button
        className="lang-selector"
        aria-label="Select language"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={`fi fi-${currentConfig.flag} lang-flag`} aria-hidden="true" />
        <span className="lang-code">{currentConfig.shortCode}</span>
      </button>

      {open && (
        <ul className="lang-dropdown" role="listbox" aria-label="Select language">
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
                  }
                }}
              >
                <span className={`fi fi-${config.flag} lang-option-flag`} aria-hidden="true" />
                <span className="lang-option-name">{config.nativeName}</span>
                <span className="lang-option-code">{config.shortCode}</span>
                {isActive && (
                  <span className="lang-option-check" aria-hidden="true">
                    ✓
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

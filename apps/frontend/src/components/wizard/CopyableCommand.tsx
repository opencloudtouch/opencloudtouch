/**
 * CopyableCommand – displays a shell command with a clipboard copy button.
 * Supports both secure (navigator.clipboard) and non-secure (execCommand fallback) contexts.
 * Markup change only: the copy button is always visible (no hover reveal, touch-safe) and uses Lucide icons.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./wizard-base.css";

interface CopyableCommandProps {
  command: string;
}

export default function CopyableCommand({ command }: CopyableCommandProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(command).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    } else {
      // Fallback for HTTP (non-secure context)
      const textarea = document.createElement("textarea");
      textarea.value = command;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } finally {
        document.body.removeChild(textarea);
      }
    }
  };

  return (
    <div className="ssh-command-wrapper">
      <pre
        className="ssh-hint-command"
        tabIndex={0} // NOSONAR(S6845): keyboard-focusable so scrollable content can be scrolled
      >
        {command}
      </pre>
      <button
        className={`ssh-copy-btn ${copied ? "copied" : ""}`}
        onClick={handleCopy}
        title={t("a11y.copyToClipboard")}
        aria-label={t("a11y.copyCommand")}
      >
        {copied ? Icon.Check(18) : Icon.Copy(18)}
      </button>
    </div>
  );
}

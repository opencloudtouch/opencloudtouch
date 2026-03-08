/**
 * CopyableCommand – displays a shell command with a clipboard copy button.
 *
 * Supports both secure (navigator.clipboard) and non-secure (execCommand fallback) contexts.
 */
import { useState } from "react";

interface CopyableCommandProps {
  command: string;
}

export default function CopyableCommand({ command }: CopyableCommandProps) {
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
      <pre className="ssh-hint-command">{command}</pre>
      <button
        className={`ssh-copy-btn ${copied ? "copied" : ""}`}
        onClick={handleCopy}
        title="In Zwischenablage kopieren"
        aria-label="Befehl kopieren"
      >
        {copied ? "✓" : "⎘"}
      </button>
    </div>
  );
}

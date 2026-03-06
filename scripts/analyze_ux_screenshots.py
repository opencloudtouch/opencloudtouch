#!/usr/bin/env python3
"""
UX Screenshot Vision Analyzer — GitHub Models API (GPT-4o Vision)

Sendet alle UX-Screenshots an die GitHub Models API und analysiert sie
auf UX/Usability-Fehler, Accessibility-Probleme und Design-Inkonsistenzen.

Anforderungen:
    - GITHUB_TOKEN_COPILOT in .env (Root des Projekts)
    - Screenshots unter apps/frontend/tests/e2e/screenshots/ux/

Aufruf:
    python tools/analyze_ux_screenshots.py
    python tools/analyze_ux_screenshots.py --limit 5       # nur erste 5
    python tools/analyze_ux_screenshots.py --model gpt-4o  # Modell wählen
    python tools/analyze_ux_screenshots.py --filter dark   # nur dark screenshots
    python tools/analyze_ux_screenshots.py --dry-run       # ohne API-Calls

Output:
    apps/frontend/tests/e2e/reports/vision/ux-vision-report.md
    apps/frontend/tests/e2e/reports/vision/ux-findings.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────

# Pfade (relativ zu diesem Script-Verzeichnis)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "apps/frontend/tests/e2e/screenshots/ux"
REPORT_DIR = PROJECT_ROOT / "apps/frontend/tests/e2e/reports/vision"

# -- GitHub Models API - eigene Rate-Limits pro Modell-Familie ----------------
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"

VISION_MODELS = {
    "gpt-4o":             "gpt-4o",
    "gpt-4o-mini":        "gpt-4o-mini",
    "gpt-4.1":            "gpt-4.1",
    "gpt-4.1-mini":       "gpt-4.1-mini",
    "llama-vision":       "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "llama-vision-large": "meta-llama/Llama-3.2-90B-Vision-Instruct",
}
DEFAULT_MODEL = "gpt-4.1"
ALL_MODELS = VISION_MODELS

# Reihenfolge der Modell-Fallbacks bei erschöpfter Tagesquota
MODEL_ROTATION_ORDER = [
    "gpt-4.1",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "llama-vision-large",
    "llama-vision",
]

# Analyse-Prompt
ANALYSIS_PROMPT = """Du bist ein erfahrener Senior UX/UI Designer und Accessibility-Experte.

Analysiere diesen Screenshot einer Web-App (Bose SoundTouch Fernbedienung, Dark-Mode Interface).
Die App läuft auf Desktop (1280x800).

Prüfe auf folgende Kategorien und liste konkrete Probleme auf:

## 1. VISUELLES DESIGN
- Farbkontrast (WCAG 2.1 AA: min. 4.5:1 für Text)
- Typography: Schriftgröße, Zeilenabstand, Lesbarkeit
- Whitespace und Layout-Dichte
- Konsistenz von Icons, Buttons, Abständen
- Visuelle Hierarchie (was ist wichtig, was nicht?)

## 2. USABILITY
- Klickziele zu klein (< 44px) oder zu nah beieinander?
- Ist der Zweck jedes Elements sofort klar?
- Gibt es fehlende Labels, Tooltips, Placeholder-Texte?
- Verwirrende oder inkonsistente Begriffe?

## 3. UX PATTERNS
- Sind Aktionen reversibel (Undo, Bestätigung vor Löschen)?
- Fehlende Feedback-States (Loading, Error, Empty, Success)?
- Inkonsistente Interaktionsmuster?
- Gibt es Dead-Ends (keine Weiterführung)?

## 4. ACCESSIBILITY
- Fehlen visuelle Fokus-Indikatoren?
- Rein farbbasierte Unterscheidungen (farbenblind-Problematik)?
- Touchziele < 44x44px?
- Fehlende oder schlechte Beschriftungen?

## FORMAT DER ANTWORT:
Für jedes gefundene Problem:
- **Severity**: [CRITICAL | HIGH | MEDIUM | LOW]
- **Kategorie**: [Design | Usability | UX | Accessibility]
- **Problem**: Kurze Beschreibung (1-2 Sätze)
- **Element**: Welches UI-Element ist betroffen?
- **Empfehlung**: Konkrete Verbesserung

Wenn ein Screenshot keine erkennbaren Probleme hat, schreibe: "✅ Kein Problem erkannt"

Sei präzise und kurz. Maximal 5 Findings pro Screenshot.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────


class RateLimitDailyExhausted(Exception):
    """Tagesquota für ein Modell erschöpft — Fallback auf nächstes Modell."""

    def __init__(self, model_key: str, wait_s: int) -> None:
        self.model_key = model_key
        self.wait_s = wait_s
        super().__init__(
            f"Modell '{model_key}': Tagesquota erschöpft "
            f"(API verlangt {wait_s}s / {wait_s // 3600:.1f}h Wartezeit)"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def load_env(env_path: Path) -> None:
    """Lädt .env Datei manuell (ohne python-dotenv Dependency)."""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def encode_image(path: Path) -> str:
    """Enkodiert Bild als base64 string."""
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def call_vision_api(
    token: str,
    model: str,
    model_key: str,
    image_base64: str,
    prompt: str,
    screenshot_name: str,
    max_retries: int = 4,
    endpoint: str = GITHUB_MODELS_ENDPOINT,
    extra_headers: dict | None = None,
) -> dict:
    """Sendet Screenshot an die GitHub Models API mit 429-Retry-Logik."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Screenshot: **{screenshot_name}**\n\n{prompt}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.3,
    }

    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(max_retries):
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                body = e.read().decode("utf-8", errors="replace")
                # Parse "Please wait X seconds" from error body
                wait_s = 65  # default
                import re
                m = re.search(r"wait\s+(\d+)\s+second", body)
                if m:
                    parsed_wait = int(m.group(1))
                    if parsed_wait > 300:
                        # Daily quota exhausted — signal caller to switch model
                        raise RateLimitDailyExhausted(model_key, parsed_wait)
                    wait_s = parsed_wait + 5
                if attempt < max_retries - 1:
                    print(f"\n    ⏳ Rate limit — warte {wait_s}s (Versuch {attempt+1}/{max_retries})...", end=" ", flush=True)
                    time.sleep(wait_s)
                else:
                    raise
            else:
                raise

    raise RuntimeError("Max retries exceeded")


def extract_text(api_response: dict) -> str:
    """Extrahiert Text aus API-Antwort."""
    try:
        return api_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return str(api_response)


# ──────────────────────────────────────────────────────────────────────────────
# Report Generierung
# ──────────────────────────────────────────────────────────────────────────────


def generate_markdown_report(findings: list[dict], model: str, duration_s: float) -> str:
    """Generiert Markdown-Report aus den Vision-Findings."""
    total = len(findings)
    errors = sum(1 for f in findings if "error" in f)
    analyzed = total - errors
    models_used = sorted({f.get("model", model) for f in findings if "error" not in f})
    models_str = ", ".join(f"`{m}`" for m in models_used) if models_used else f"`{model}`"

    dark_count = sum(1 for f in findings if "__dark" in f.get("screenshot", "").lower() and "error" not in f)
    light_count = sum(1 for f in findings if "__light" in f.get("screenshot", "").lower() and "error" not in f)

    lines = [
        "# UX Vision Analysis\n",
        f"**Erstellt**: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Primärmodell**: `{model}` (GitHub Models API)  ",
        f"**Genutzte Modelle**: {models_str}  ",
        f"**Screenshots analysiert**: {analyzed}/{total} ({dark_count} dark, {light_count} light)  ",
        f"**Laufzeit**: {duration_s:.0f}s  ",
        "\n---\n",
    ]

    for finding in findings:
        name = finding.get("screenshot", "?")
        used_model = finding.get("model", model)
        model_badge = f" *(via {used_model})*" if used_model != model else ""
        lines.append(f"\n## {name}{model_badge}\n")

        if "error" in finding:
            lines.append(f"⚠️ **API Fehler**: `{finding['error']}`\n")
            continue

        analysis = finding.get("analysis", "")
        lines.append(analysis)
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    # Ensure UTF-8 output on Windows (avoids cp1252 encoding errors with emoji)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="UX Screenshot Vision Analyzer")
    parser.add_argument("--limit", type=int, default=0, help="Anzahl Screenshots (0 = alle)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=list(ALL_MODELS.keys()),
        help=f"Vision-Modell (GitHub Models API). Verfuegbar: {', '.join(VISION_MODELS)}",
    )
    parser.add_argument("--filter", default="", help="Filter: 'dark', 'light', oder Substring des Dateinamens")
    parser.add_argument("--dry-run", action="store_true", help="Keine API-Calls, nur Dateiliste")
    parser.add_argument(
        "--delay",
        type=float,
        default=7.0,
        help="Verzögerung zwischen API-Calls in Sekunden (Rate-Limiting, min 7s empfohlen)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Bereits analysierte Screenshots überspringen (liest vorhandenes JSON)",
    )
    parser.add_argument(
        "--no-theme-order",
        action="store_true",
        help="Theme-Sortierung deaktivieren (Standard: erst dark, dann light)",
    )
    args = parser.parse_args()

    # .env laden
    load_env(PROJECT_ROOT / ".env")
    load_env(PROJECT_ROOT / ".env.local")

    github_pat = os.environ.get("GITHUB_TOKEN_COPILOT", "")
    if not github_pat and not args.dry_run:
        print("GITHUB_TOKEN_COPILOT nicht gefunden in .env oder .env.local")
        print("   Setze GITHUB_TOKEN_COPILOT=<dein_github_pat> in .env")
        return 1

    # Alle Modelle gehen direkt ueber GitHub Models API mit dem PAT
    token = github_pat
    api_endpoint = GITHUB_MODELS_ENDPOINT
    extra_headers: dict | None = None

    # Modell-Rotation: starte mit gewähltem Modell, falle bei Quota-Erschöpfung zurück
    rotation = [m for m in MODEL_ROTATION_ORDER if m in ALL_MODELS]
    # Gewähltes Modell an den Anfang stellen (falls nicht in Rotation, trotzdem hinzufügen)
    if args.model in rotation:
        rotation.remove(args.model)
    rotation.insert(0, args.model)

    current_model_key = args.model
    api_model = ALL_MODELS[current_model_key]
    exhausted_models: set[str] = set()

    # Screenshots finden
    if not SCREENSHOTS_DIR.exists():
        print(f"❌ Screenshots-Verzeichnis nicht gefunden: {SCREENSHOTS_DIR}")
        print("   Führ zuerst 'npm run test:ux' aus")
        return 1

    screenshots = sorted(SCREENSHOTS_DIR.rglob("*.png"))

    # Filter anwenden
    if args.filter:
        screenshots = [s for s in screenshots if args.filter.lower() in s.name.lower()]

    # Theme-Sortierung: erst dark, dann light (ermöglicht early findings während light läuft)
    if not args.no_theme_order:
        def _theme_key(p: Path) -> tuple[int, str]:
            name = p.name.lower()
            # dark=0, light=1, sonstige=2
            if "__dark" in name:
                return (0, p.name)
            if "__light" in name:
                return (1, p.name)
            return (2, p.name)
        screenshots = sorted(screenshots, key=_theme_key)

    # Limit
    if args.limit > 0:
        screenshots = screenshots[: args.limit]

    if not screenshots:
        print(f"❌ Keine Screenshots gefunden in: {SCREENSHOTS_DIR}")
        return 1

    if not args.no_theme_order and not args.filter:
        dark_count = sum(1 for s in screenshots if "__dark" in s.name.lower())
        light_count = sum(1 for s in screenshots if "__light" in s.name.lower())
        print(f"📸 {len(screenshots)} Screenshots gefunden ({dark_count} dark-first, dann {light_count} light)")
    else:
        print(f"📸 {len(screenshots)} Screenshots gefunden")
    print(f"🤖 Primärmodell: {args.model} → {api_model}")
    print(f"🔄 Fallback-Rotation: {' → '.join(m for m in rotation if m != args.model)}")
    if args.dry_run:
        print("🔍 Dry-Run — keine API-Calls\n")
        for s in screenshots:
            print(f"   {s.name}")
        return 0

    # Report-Verzeichnis anlegen
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Resume: bereits analysierte Screenshots laden
    already_done: set[str] = set()
    findings: list[dict] = []
    json_path = REPORT_DIR / "ux-findings.json"
    if args.resume and json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            existing = json.load(f)
        all_findings = existing.get("findings", [])
        # Nur erfolgreiche Findings behalten — fehlerhafte werden erneut versucht
        findings = [f for f in all_findings if "error" not in f]
        skipped_errors = len(all_findings) - len(findings)
        already_done = {f["screenshot"] for f in findings}
        retry_msg = f", {skipped_errors} fehlerhafte werden erneut versucht" if skipped_errors else ""
        print(f"📂 Resume: {len(already_done)} bereits analysiert — überspringen{retry_msg}")

    start_time = time.time()

    def save_incremental() -> None:
        """Save findings to JSON after each screenshot (crash-resilient)."""
        models_used = sorted({f.get("model", args.model) for f in findings})
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "generated_at": datetime.now().isoformat(),
                    "primary_model": args.model,
                    "models_used": models_used,
                    "screenshot_count": len(findings),
                    "findings": findings,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

    for i, screenshot_path in enumerate(screenshots, 1):
        name = screenshot_path.name
        if name in already_done:
            print(f"  [{i:02d}/{len(screenshots):02d}] {name} ... ⏭ (bereits vorhanden)")
            continue
        print(f"  [{i:02d}/{len(screenshots):02d}] {name} ...", end=" ", flush=True)

        # Encode image once; retry loop cycles through models on daily-quota exhaustion
        image_b64 = encode_image(screenshot_path)
        screenshot_done = False
        while not screenshot_done:
            try:
                response = call_vision_api(
                    token=token,
                    model=api_model,
                    model_key=current_model_key,
                    image_base64=image_b64,
                    prompt=ANALYSIS_PROMPT,
                    screenshot_name=name,
                    endpoint=api_endpoint,
                    extra_headers=extra_headers,
                )
                analysis_text = extract_text(response)
                findings.append({"screenshot": name, "model": current_model_key, "analysis": analysis_text})
                print(f"✅  [{current_model_key}]")
                screenshot_done = True
            except RateLimitDailyExhausted as rle:
                exhausted_models.add(current_model_key)
                print(f"\n    ⚠️  {rle}")
                next_key = next((m for m in rotation if m not in exhausted_models), None)
                if next_key is None:
                    print("\n❌ Alle Modelle in der Rotation erschöpft. Stoppe — bitte morgen mit --resume fortsetzen.")
                    save_incremental()
                    return 1
                current_model_key = next_key
                api_model = ALL_MODELS[current_model_key]
                print(f"    🔄 Wechsle zu Modell: {current_model_key} → {api_model}")
                # loop continues → retry with new model
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                msg = f"HTTP {e.code}: {error_body[:200]}"
                findings.append({"screenshot": name, "model": current_model_key, "error": msg})
                print(f"❌ {msg}")
                screenshot_done = True
            except Exception as e:  # noqa: BLE001
                findings.append({"screenshot": name, "model": current_model_key, "error": str(e)})
                print(f"❌ {e}")
                screenshot_done = True

        # Incremental save after each screenshot (crash-resilient)
        save_incremental()

        # Rate-Limiting Pause (außer beim letzten)
        if i < len(screenshots):
            time.sleep(args.delay)

    duration = time.time() - start_time

    # JSON speichern (finaler Save — save_incremental hat bereits nach jedem Screenshot gespeichert)
    save_incremental()

    # Markdown speichern
    md_path = REPORT_DIR / "ux-vision-report.md"
    md_content = generate_markdown_report(findings, args.model, duration)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    errors = sum(1 for f in findings if "error" in f)
    models_used_summary = ", ".join(sorted({f.get("model", args.model) for f in findings if "error" not in f}))
    print(f"\n{'─' * 60}")
    print(f"✅ Analyse abgeschlossen in {duration:.0f}s")
    print(f"   Screenshots analysiert: {len(findings) - errors}/{len(findings)}")
    print(f"   Genutzte Modelle: {models_used_summary}")
    print(f"   Fehler: {errors}")
    print(f"\n📋 Report: {md_path}")
    print(f"📊 JSON:   {json_path}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

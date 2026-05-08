/**
 * Step 2: USB Preparation
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./Step2USBPreparation.css";

interface Step2Props {
  deviceModel: string;
  onNext: () => void;
  onPrevious: () => void;
}

type Platform = "windows" | "macos" | "linux" | "unknown";

function detectPlatform(): Platform {
  const userAgent = navigator.userAgent.toLowerCase();
  const plat = navigator.platform?.toLowerCase();
  if (plat?.includes("win") || userAgent.includes("windows")) return "windows";
  if (plat?.includes("mac") || userAgent.includes("mac")) return "macos";
  if (plat?.includes("linux") || userAgent.includes("linux")) return "linux";
  return "unknown";
}

export default function Step2USBPreparation({ deviceModel, onNext, onPrevious }: Step2Props) {
  const { t } = useTranslation();
  const [platform, setPlatform] = useState<Platform>(detectPlatform);
  const [usbReady, setUsbReady] = useState(false);

  const usbPort = deviceModel.includes("30") || deviceModel.includes("300") ? "USB-A" : "Micro-USB";

  const getFormatInstructions = (): { title: string; steps: string[] } => {
    switch (platform) {
      case "windows":
        return {
          title: t("setup.wizard.step2.platformWindowsTitle"),
          steps: [
            t("setup.wizard.step2.windowsStep1"),
            t("setup.wizard.step2.windowsStep2"),
            t("setup.wizard.step2.windowsStep3"),
            t("setup.wizard.step2.windowsStep4"),
            t("setup.wizard.step2.windowsStep5"),
            t("setup.wizard.step2.windowsStep6"),
          ],
        };
      case "macos":
        return {
          title: t("setup.wizard.step2.platformMacTitle"),
          steps: [
            t("setup.wizard.step2.macStep1"),
            t("setup.wizard.step2.macStep2"),
            t("setup.wizard.step2.macStep3"),
            t("setup.wizard.step2.macStep4"),
            t("setup.wizard.step2.macStep5"),
            t("setup.wizard.step2.macStep6"),
            t("setup.wizard.step2.macStep7"),
          ],
        };
      case "linux":
        return {
          title: t("setup.wizard.step2.platformLinuxTitle"),
          steps: [
            t("setup.wizard.step2.linuxStep1"),
            t("setup.wizard.step2.linuxStep2"),
            t("setup.wizard.step2.linuxStep3"),
            t("setup.wizard.step2.linuxStep4"),
            t("setup.wizard.step2.linuxStep5"),
          ],
        };
      default:
        return {
          title: t("setup.wizard.step2.platformDefaultTitle"),
          steps: [t("setup.wizard.step2.defaultStep1"), t("setup.wizard.step2.defaultStep2")],
        };
    }
  };

  const formatInstructions = getFormatInstructions();

  return (
    <WizardStep
      stepNumber={1}
      title={t("setup.wizard.step2.title")}
      description={t("setup.wizard.step2.description")}
      warning={t("setup.wizard.step2.warning")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!usbReady}
      nextDisabledReason={t("setup.wizard.step2.nextDisabled")}
    >
      <div className="usb-preparation">
        {/* Device Info */}
        <div className="usb-device-info">
          <div className="usb-icon">🔌</div>
          <div className="usb-device-details">
            <strong>{t("setup.wizard.step2.deviceNeeds")}</strong> {usbPort}
            <br />
            <small>
              {t("setup.wizard.step2.model")} {deviceModel}
            </small>
          </div>
        </div>

        {/* Format Instructions */}
        <div className="usb-section">
          <div className="usb-section-header">
            <h3 className="usb-section-title">
              <span className="usb-section-number">1</span>
              {formatInstructions.title}
            </h3>
            <label htmlFor="usb-platform-select" className="usb-platform-label">
              {t("setup.wizard.step2.platformLabel")}
            </label>
            <select
              id="usb-platform-select"
              className="usb-platform-select"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
              aria-label={t("setup.wizard.step2.platformAriaLabel")}
            >
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="linux">Linux</option>
            </select>
          </div>
          <ol className="usb-instruction-list">
            {formatInstructions.steps.map((step) => (
              <li key={step} className="usb-instruction-item">
                {step}
              </li>
            ))}
          </ol>
        </div>

        {/* Create File */}
        <div className="usb-section">
          <h3 className="usb-section-title">
            <span className="usb-section-number">2</span>
            {t("setup.wizard.step2.sectionCreateFile")}
          </h3>
          <p className="usb-section-description">{t("setup.wizard.step2.createFileDesc")}</p>
        </div>

        {/* Verification */}
        <div className="usb-section">
          <h3 className="usb-section-title">
            <span className="usb-section-number">3</span>
            {t("setup.wizard.step2.sectionVerify")}
          </h3>
          <div className="usb-checklist">
            <label className="usb-checklist-item">
              <input type="checkbox" />
              <span>{t("setup.wizard.step2.checkFat32")}</span>
            </label>
            <label className="usb-checklist-item">
              <input type="checkbox" />
              <span>{t("setup.wizard.step2.checkFileEmpty")}</span>
            </label>
            <label className="usb-checklist-item">
              <input
                type="checkbox"
                checked={usbReady}
                onChange={(e) => setUsbReady(e.target.checked)}
              />
              <span>
                <strong>{t("setup.wizard.step2.checkReady")}</strong>
              </span>
            </label>
          </div>
        </div>
      </div>
    </WizardStep>
  );
}

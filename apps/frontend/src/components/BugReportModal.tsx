import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { submitBugReport } from "../api/bugReport";
import { getLogEntries } from "../utils/logBuffer";
import { useToast } from "../contexts/ToastContext";
import "./BugReportModal.css";

interface BugReportModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
}

const INSTALLATION_OPTIONS = [
  { value: "docker", label: "Docker (Raspberry Pi)" },
  { value: "docker-other", label: "Docker (other hardware)" },
  { value: "source", label: "From Source" },
  { value: "other", label: "Other" },
];

const HARDWARE_OPTIONS = [
  { value: "raspberry-pi-4", label: "Raspberry Pi 4" },
  { value: "raspberry-pi-5", label: "Raspberry Pi 5" },
  { value: "linux-x64", label: "Linux x86_64" },
  { value: "other", label: "Other" },
];

const DEVICE_OPTIONS = [
  "SoundTouch 10",
  "SoundTouch 20",
  "SoundTouch 30",
  "SoundTouch 300",
  "SoundTouch Portable",
  "Lifestyle 535",
  "Lifestyle 600",
  "Lifestyle 650",
  "Wave SoundTouch",
  "Other",
];

const NETWORK_OPTIONS = [
  { value: "wifi", label: "Wi-Fi" },
  { value: "lan", label: "LAN / Ethernet" },
  { value: "mixed", label: "Mixed" },
];

export default function BugReportModal({ open, onClose }: BugReportModalProps) {
  const { show: showToast } = useToast();
  const location = useLocation();
  const closeRef = useRef<HTMLButtonElement>(null);
  const clickTimestampRef = useRef<number>(0);

  const [submitting, setSubmitting] = useState(false);
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState("");
  const [expected, setExpected] = useState("");
  const [installationType, setInstallationType] = useState("");
  const [hardware, setHardware] = useState("");
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [networkConfig, setNetworkConfig] = useState("");
  const [additionalInfo, setAdditionalInfo] = useState("");
  const [otherInstallation, setOtherInstallation] = useState("");
  const [otherHardware, setOtherHardware] = useState("");
  const [otherDevice, setOtherDevice] = useState("");

  useEffect(() => {
    if (open) {
      clickTimestampRef.current = Date.now() / 1000;
      closeRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  const resetForm = useCallback(() => {
    setDescription("");
    setSteps("");
    setExpected("");
    setInstallationType("");
    setHardware("");
    setSelectedDevices([]);
    setNetworkConfig("");
    setAdditionalInfo("");
    setOtherInstallation("");
    setOtherHardware("");
    setOtherDevice("");
  }, []);

  const captureScreenshot = async (): Promise<string> => {
    try {
      const { default: html2canvas } = await import("html2canvas");
      const canvas = await html2canvas(document.body, {
        scale: 0.5,
        logging: false,
        useCORS: true,
        width: Math.min(document.body.scrollWidth, 1280),
      });
      return canvas.toDataURL("image/jpeg", 0.6);
    } catch {
      return "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const screenshot = await captureScreenshot();
      const browserInfo = `${navigator.userAgent} | ${window.innerWidth}x${window.innerHeight}`;

      const result = await submitBugReport({
        description,
        steps_to_reproduce: steps,
        expected_behavior: expected,
        installation_type: installationType,
        hardware,
        soundtouch_devices: selectedDevices,
        network_config: networkConfig,
        additional_info: additionalInfo,
        other_installation: otherInstallation,
        other_hardware: otherHardware,
        other_device: otherDevice,
        screenshot_data_url: screenshot,
        frontend_logs: getLogEntries(),
        browser_info: browserInfo,
        current_route: location.pathname,
        click_timestamp: clickTimestampRef.current,
      });

      showToast(`Bug report created! ${result.issue_url}`, "success", 10000);
      resetForm();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      showToast(`Failed to submit bug report: ${msg}`, "error", 8000);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleDevice = (device: string) => {
    setSelectedDevices((prev) =>
      prev.includes(device) ? prev.filter((d) => d !== device) : [...prev, device]
    );
  };

  const needsOtherInstallation = installationType === "other";
  const needsOtherHardware = hardware === "other";
  const needsOtherDevice = selectedDevices.includes("Other");

  const isValid =
    description.length >= 10 &&
    steps.length >= 10 &&
    expected.length >= 5 &&
    installationType !== "" &&
    hardware !== "" &&
    (!needsOtherInstallation || otherInstallation.length >= 2) &&
    (!needsOtherHardware || otherHardware.length >= 2) &&
    (!needsOtherDevice || otherDevice.length >= 2);

  if (!open) return null;

  return (
    <div className="bug-modal-overlay">
      <dialog className="bug-modal" open aria-labelledby="bug-modal-title" onCancel={onClose}>
        <div className="bug-modal-header">
          <h2 id="bug-modal-title">🐛 Report a Bug</h2>
          <button ref={closeRef} className="bug-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <form className="bug-modal-form" onSubmit={handleSubmit}>
          {/* 1. Bug Description */}
          <label className="bug-field">
            <span className="bug-label">
              Bug Description <span className="bug-required">*</span>
            </span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What went wrong?"
              rows={3}
              required
              minLength={10}
              maxLength={2000}
            />
          </label>

          {/* 2. Steps to Reproduce */}
          <label className="bug-field">
            <span className="bug-label">
              Steps to Reproduce <span className="bug-required">*</span>
            </span>
            <textarea
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
              placeholder="1. Go to...&#10;2. Click on...&#10;3. See error..."
              rows={3}
              required
              minLength={10}
              maxLength={2000}
            />
          </label>

          {/* 3. Expected Behavior */}
          <label className="bug-field">
            <span className="bug-label">
              Expected Behavior <span className="bug-required">*</span>
            </span>
            <textarea
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              placeholder="What should have happened?"
              rows={2}
              required
              minLength={5}
              maxLength={1000}
            />
          </label>

          {/* 4. Installation Type */}
          <label className="bug-field">
            <span className="bug-label">
              Installation Type <span className="bug-required">*</span>
            </span>
            <select
              value={installationType}
              onChange={(e) => setInstallationType(e.target.value)}
              required
            >
              <option value="">Select...</option>
              {INSTALLATION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {needsOtherInstallation && (
            <label className="bug-field bug-field--other">
              <span className="bug-label">
                Which installation? <span className="bug-required">*</span>
              </span>
              <input
                type="text"
                value={otherInstallation}
                onChange={(e) => setOtherInstallation(e.target.value)}
                placeholder="e.g. Synology DSM, Proxmox..."
                required
                minLength={2}
              />
            </label>
          )}

          {/* 5. Hardware / Platform */}
          <label className="bug-field">
            <span className="bug-label">
              Hardware / Platform <span className="bug-required">*</span>
            </span>
            <select value={hardware} onChange={(e) => setHardware(e.target.value)} required>
              <option value="">Select...</option>
              {HARDWARE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {needsOtherHardware && (
            <label className="bug-field bug-field--other">
              <span className="bug-label">
                Which hardware? <span className="bug-required">*</span>
              </span>
              <input
                type="text"
                value={otherHardware}
                onChange={(e) => setOtherHardware(e.target.value)}
                placeholder="e.g. Odroid N2+, Intel NUC..."
                required
                minLength={2}
              />
            </label>
          )}

          {/* 6. SoundTouch Devices */}
          <fieldset className="bug-field">
            <legend className="bug-label">SoundTouch Device(s)</legend>
            <div className="bug-checkbox-group">
              {DEVICE_OPTIONS.map((device) => (
                <label key={device} className="bug-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedDevices.includes(device)}
                    onChange={() => toggleDevice(device)}
                  />
                  {device}
                </label>
              ))}
            </div>
          </fieldset>
          {needsOtherDevice && (
            <label className="bug-field bug-field--other">
              <span className="bug-label">
                Which device? <span className="bug-required">*</span>
              </span>
              <input
                type="text"
                value={otherDevice}
                onChange={(e) => setOtherDevice(e.target.value)}
                placeholder="e.g. Bose Companion..."
                required
                minLength={2}
              />
            </label>
          )}

          {/* 7. Network Configuration */}
          <label className="bug-field">
            <span className="bug-label">Network Configuration</span>
            <select value={networkConfig} onChange={(e) => setNetworkConfig(e.target.value)}>
              <option value="">Select...</option>
              {NETWORK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          {/* 8. Additional Info */}
          <label className="bug-field">
            <span className="bug-label">Additional Info</span>
            <textarea
              value={additionalInfo}
              onChange={(e) => setAdditionalInfo(e.target.value)}
              placeholder="Any extra context, logs, timeline..."
              rows={2}
              maxLength={2000}
            />
          </label>

          {/* Submit */}
          <div className="bug-modal-actions">
            <button
              type="button"
              className="bug-btn bug-btn--cancel"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bug-btn bug-btn--submit"
              disabled={!isValid || submitting}
            >
              {submitting ? "Submitting..." : "Submit Bug Report"}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

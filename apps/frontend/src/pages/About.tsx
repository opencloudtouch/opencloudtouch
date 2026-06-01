import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useState, useEffect } from "react";
import { useHealth } from "../hooks/useHealth";
import { Skeleton } from "../components/LoadingSkeleton";
import "./About.css";

const GITHUB_REPO = "opencloudtouch/opencloudtouch";
const GITHUB_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;
const BMC_URL = "https://buymeacoffee.com/b49rjg5k6vj";

interface Supporter {
  name: string;
  type: "monthly" | "one-time";
  amount: number;
  monthlyAmount: number;
  firstSupportDate: string;
}

interface UpdateInfo {
  available: boolean;
  latestVersion?: string;
  releaseUrl?: string;
  releaseNotes?: string;
}

export default function About() {
  const { t } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealth();

  const [supporters, setSupporters] = useState<Supporter[]>([]);
  const [supportersLoading, setSupportersLoading] = useState(true);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [updateLoading, setUpdateLoading] = useState(true);

  // Load supporters from CSV
  useEffect(() => {
    const loadSupporters = async () => {
      try {
        const response = await fetch("/supporters.csv");
        if (!response.ok) {
          // CSV not found or empty - not an error, just no supporters yet
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        const text = await response.text();
        const lines = text.trim().split("\n").slice(1); // Skip header

        if (lines.length === 0 || lines[0] === "") {
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        const parsed: Supporter[] = lines
          .filter((line) => line.trim())
          .map((line) => {
            const [name, type, amount, monthlyAmount, firstSupportDate] = line.split(",");
            return {
              name: name.trim(),
              type: type.trim() as "monthly" | "one-time",
              amount: parseFloat(amount),
              monthlyAmount: parseFloat(monthlyAmount),
              firstSupportDate: firstSupportDate.trim(),
            };
          });

        // Sort by ranking formula: amount + monthlyAmount DESC, then by date ASC, then alphabetically
        parsed.sort((a, b) => {
          const scoreA = a.amount + a.monthlyAmount;
          const scoreB = b.amount + b.monthlyAmount;

          if (scoreB !== scoreA) return scoreB - scoreA;

          // Tie-breaker: earlier supporter wins
          if (a.firstSupportDate !== b.firstSupportDate) {
            return a.firstSupportDate.localeCompare(b.firstSupportDate);
          }

          // Final tie-breaker: alphabetical
          return a.name.localeCompare(b.name);
        });

        setSupporters(parsed);
        setSupportersLoading(false);
      } catch (error) {
        console.error("Failed to load supporters:", error);
        setSupporters([]);
        setSupportersLoading(false);
      }
    };

    loadSupporters();
  }, []);

  // Check for updates
  useEffect(() => {
    const checkUpdate = async () => {
      if (!health?.version) {
        setUpdateLoading(false);
        return;
      }

      try {
        const response = await fetch(GITHUB_API);
        if (!response.ok) {
          setUpdateLoading(false);
          return;
        }

        const release = await response.json();
        const latestTag = release.tag_name?.replace(/^v/, ""); // Remove 'v' prefix
        const currentVersion = health.version;

        // Simple version comparison
        const isNewer = latestTag && latestTag !== currentVersion;

        setUpdateInfo({
          available: isNewer,
          latestVersion: latestTag,
          releaseUrl: release.html_url,
          releaseNotes: release.body,
        });
        setUpdateLoading(false);
      } catch (error) {
        console.error("Failed to check for updates:", error);
        setUpdateLoading(false);
      }
    };

    // Only check after health is loaded and if >3s passed (per user requirement)
    if (health?.version) {
      const timer = setTimeout(checkUpdate, 3000);
      return () => clearTimeout(timer);
    }
  }, [health?.version]);

  const monthlySupporters = supporters.filter((s) => s.type === "monthly");
  const oneTimeSupporters = supporters.filter((s) => s.type === "one-time");

  return (
    <div className="about-page">
      <motion.div
        className="about-container"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Header */}
        <div className="about-header">
          <div className="about-icon">🎵</div>
          <h1 className="about-title">OpenCloudTouch</h1>
          {healthLoading && <Skeleton width="60px" height="24px" borderRadius="20px" />}
          {!healthLoading && health && <span className="about-version">v{health.version}</span>}
        </div>

        {/* Build Info */}
        {!healthLoading && health?.uptime && (
          <p className="about-build-time">
            {t("about.buildTime", {
              time: new Date(Date.now() - health.uptime * 1000).toLocaleString(),
            })}
          </p>
        )}

        {/* Update Check */}
        <div className="about-update-section">
          {updateLoading && (
            <div className="about-update-loading">
              <div className="spinner-small" />
              <span>{t("about.checkingUpdates")}</span>
            </div>
          )}
          {!updateLoading && updateInfo.available && (
            <motion.div
              className="about-update-available"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <div className="update-icon">🆕</div>
              <div className="update-content">
                <p className="update-title">
                  {t("about.updateAvailable", { version: updateInfo.latestVersion })}
                </p>
                <div className="update-actions">
                  <a
                    href={updateInfo.releaseUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary btn-sm"
                  >
                    {t("about.viewRelease")}
                  </a>
                </div>
              </div>
            </motion.div>
          )}
          {!updateLoading && !updateInfo.available && health && (
            <div className="about-update-current">
              <span className="update-check-icon">✅</span>
              <span>{t("about.upToDate")}</span>
            </div>
          )}
        </div>

        {/* Supporters Section */}
        {!supportersLoading && supporters.length > 0 && (
          <motion.div
            className="about-supporters-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="supporters-title">💛 {t("about.supportersTitle")}</h2>
            <p className="supporters-description">{t("about.supportersDescription")}</p>

            {/* Monthly Supporters */}
            {monthlySupporters.length > 0 && (
              <div className="supporters-group">
                <h3 className="supporters-group-title">{t("about.monthlySupporters")}</h3>
                <div className="supporters-list">
                  {monthlySupporters.map((supporter, index) => (
                    <div key={`${supporter.name}-${index}`} className="supporter-card">
                      <div className="supporter-rank">🥇</div>
                      <div className="supporter-info">
                        <span className="supporter-name">{supporter.name}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* One-Time Supporters */}
            {oneTimeSupporters.length > 0 && (
              <div className="supporters-group">
                <h3 className="supporters-group-title">{t("about.oneTimeSupporters")}</h3>
                <div className="supporters-list">
                  {oneTimeSupporters.map((supporter, index) => (
                    <div key={`${supporter.name}-${index}`} className="supporter-card">
                      <div className="supporter-rank">☕</div>
                      <div className="supporter-info">
                        <span className="supporter-name">{supporter.name}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Support CTA */}
            <div className="support-cta">
              <p>{t("about.supportCTA")}</p>
              <a
                href={BMC_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primary"
              >
                ☕ {t("about.supportButton")}
              </a>
            </div>
          </motion.div>
        )}

        {/* Empty state - no supporters yet */}
        {!supportersLoading && supporters.length === 0 && (
          <motion.div
            className="about-supporters-empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <div className="empty-icon">💛</div>
            <p className="empty-title">{t("about.noSupportersYet")}</p>
            <p className="empty-description">{t("about.supportCTA")}</p>
            <a href={BMC_URL} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
              ☕ {t("about.supportButton")}
            </a>
          </motion.div>
        )}

        {/* Links */}
        <div className="about-links">
          <a
            href={`https://github.com/${GITHUB_REPO}`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link"
          >
            🐙 GitHub
          </a>
          <a
            href={`https://github.com/${GITHUB_REPO}/issues`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link"
          >
            🐛 {t("about.reportIssue")}
          </a>
        </div>
      </motion.div>
    </div>
  );
}

import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useState, useEffect } from "react";
import { useHealth } from "../hooks/useHealth";
import { Skeleton } from "../components/LoadingSkeleton";
import {
  type Supporter,
  type UpdateInfo,
  parseCSVLine,
  getRandomThankYou,
  getFontSize,
  generateGradientColor,
  cleanName,
} from "./aboutUtils";
import "./About.css";

const GITHUB_REPO = "opencloudtouch/opencloudtouch";
const GITHUB_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;
const BMC_URL = "https://buymeacoffee.com/b49rjg5k6vj";

export default function About() {
  const { t, i18n } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealth();

  const [supporters, setSupporters] = useState<Supporter[]>([]);
  const [supportersLoading, setSupportersLoading] = useState(true);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [updateLoading, setUpdateLoading] = useState(true);

  // Load supporters from CSV
  useEffect(() => {
    const loadSupporters = async () => {
      try {
        // Cache-busting: Add timestamp to prevent stale data
        const response = await fetch(`/supporters.csv?t=${Date.now()}`);
        if (!response.ok) {
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        let text = await response.text();

        // Strip UTF-8 BOM if present
        if (text.codePointAt(0) === 0xfeff) {
          text = text.substring(1);
        }

        const lines = text.trim().split("\n").slice(1); // Skip header

        if (lines.length === 0 || lines[0] === "") {
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        const parsed: Supporter[] = lines
          .filter((line) => line.trim())
          .map((line) => parseCSVLine(line))
          .filter((fields): fields is string[] => fields.length >= 5)
          .map((fields) => ({
            name: fields[0],
            type: fields[1] as "monthly" | "one-time",
            amount: Number.parseFloat(fields[2]) || 0,
            monthlyAmount: Number.parseFloat(fields[3]) || 0,
            firstSupportDate: fields[4],
          }));

        // Sort: amount DESC, then monthlyAmount DESC, then firstSupportDate ASC (older first)
        parsed.sort((a, b) => {
          if (b.amount !== a.amount) return b.amount - a.amount;
          if (b.monthlyAmount !== a.monthlyAmount) return b.monthlyAmount - a.monthlyAmount;
          return a.firstSupportDate.localeCompare(b.firstSupportDate);
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
        const latestTag = release.tag_name?.replace(/^v/, "");
        const currentVersion = health.version;
        const isNewer = latestTag && latestTag !== currentVersion;

        setUpdateInfo({
          available: isNewer,
          latestVersion: latestTag,
          releaseUrl: release.html_url,
        });
        setUpdateLoading(false);
      } catch (error) {
        console.error("Failed to check for updates:", error);
        setUpdateLoading(false);
      }
    };

    if (health?.version) {
      const timer = setTimeout(checkUpdate, 3000);
      return () => clearTimeout(timer);
    }
  }, [health?.version]);

  const maxAmount = Math.max(...supporters.map((s) => s.amount + s.monthlyAmount), 1);

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
                <a
                  href={updateInfo.releaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary btn-sm"
                >
                  {t("about.viewRelease")}
                </a>
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

        {/* Supporters Wimmelbild */}
        {!supportersLoading && supporters.length > 0 && (
          <motion.div
            className="supporters-wimmelbild-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="supporters-wimmelbild-title">Supp❤️rters</h2>

            <div className="supporters-wimmelbild">
              {supporters.map((supporter, index) => {
                const fontSize = getFontSize(supporter, maxAmount);
                const color = generateGradientColor(index, supporters.length);
                const isMonthly = supporter.monthlyAmount > 0;
                const supporterKey = `${supporter.name}-${index}`;

                return (
                  <motion.span
                    key={supporterKey}
                    className={
                      isMonthly ? "supporter-name-wimmelbild monthly" : "supporter-name-wimmelbild"
                    }
                    style={{
                      fontSize: `${fontSize}px`,
                      color: isMonthly ? undefined : color,
                    }}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.02 }}
                    title={getRandomThankYou(isMonthly, i18n.language)}
                    onMouseEnter={(e) => {
                      e.currentTarget.title = getRandomThankYou(isMonthly, i18n.language);
                    }}
                  >
                    {cleanName(supporter.name)}
                  </motion.span>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Links */}
        <div className="about-links-simple">
          <a
            href={`https://github.com/${GITHUB_REPO}`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple"
          >
            <svg className="icon-github" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub›
          </a>
          <a
            href={`https://github.com/${GITHUB_REPO}/issues/new?template=bug_report.yml`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple"
          >
            🐛 {t("about.reportBug")}›
          </a>
          <a
            href={BMC_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple about-link-support"
          >
            ☕ {t("about.support")}›
          </a>
        </div>
      </motion.div>
    </div>
  );
}

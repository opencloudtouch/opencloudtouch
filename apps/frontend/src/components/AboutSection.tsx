import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useHealth } from "../hooks/useHealth";
import { useDevices } from "../hooks/useDevices";
import { Skeleton } from "./LoadingSkeleton";
import "./AboutSection.css";

const GITHUB_URL = "https://github.com/scheilch/opencloudtouch";
const ISSUES_URL = "https://github.com/scheilch/opencloudtouch/issues/new?template=bug_report.yml";
const BMC_URL = "https://buymeacoffee.com/b49rjg5k6vj";

export default function AboutSection() {
  const { t } = useTranslation();
  const { data: health, isLoading: healthLoading, isError: healthError } = useHealth();
  const { data: devices, isLoading: devicesLoading } = useDevices();

  const deviceCount = devices?.length ?? 0;

  const links = [
    { icon: "\uD83D\uDC19", label: t("about.github"), href: GITHUB_URL },
    { icon: "\uD83D\uDC1B", label: t("about.reportIssue"), href: ISSUES_URL },
    ...(BMC_URL ? [{ icon: "\u2615", label: t("about.support"), href: BMC_URL }] : []),
  ];

  return (
    <motion.section
      className="settings-section about-section"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
    >
      <h2 className="section-title">
        <span className="section-icon">{"\u2139\uFE0F"}</span>
        {t("about.sectionTitle")}
      </h2>

      <div className="settings-card about-card">
        {/* App header row */}
        <div className="about-app-header">
          <div className="about-app-icon">{"\uD83C\uDFB5"}</div>
          <div className="about-app-info">
            <div className="about-name-row">
              <span className="about-app-name">OpenCloudTouch</span>
              {healthLoading && <Skeleton width="44px" height="18px" borderRadius="20px" />}
              {!healthLoading && healthError && (
                <span className="about-version-error">{t("about.versionUnavailable")}</span>
              )}
              {!healthLoading && !healthError && health && (
                <span className="about-version-badge">v{health.version}</span>
              )}
            </div>
            <p className="about-app-description">{t("about.appDescription")}</p>
          </div>
        </div>

        <hr className="about-divider" />

        {/* Device count row */}
        <div className="about-meta-row">
          <span className="about-meta-icon">{"\uD83D\uDD0A"}</span>
          {devicesLoading ? (
            <Skeleton width="140px" height="14px" borderRadius="4px" />
          ) : (
            <span className="about-meta-text">
              {t("about.devicesConnected", { count: deviceCount })}
            </span>
          )}
        </div>

        <hr className="about-divider" />

        {/* External links */}
        <ul className="about-links">
          {links.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="about-link-item"
              >
                <span className="about-link-icon">{link.icon}</span>
                <span className="about-link-label">{link.label}</span>
                <span className="about-link-chevron">{"\u203A"}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </motion.section>
  );
}

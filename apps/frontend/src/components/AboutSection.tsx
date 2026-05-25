import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useHealth } from "../hooks/useHealth";
import { useDevices } from "../hooks/useDevices";
import { Skeleton } from "./LoadingSkeleton";
import "./AboutSection.css";

const GITHUB_URL = "https://github.com/opencloudtouch/opencloudtouch";
const ISSUES_URL =
  "https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml";
const BMC_URL = "https://buymeacoffee.com/b49rjg5k6vj";

const CONTRIBUTORS = [
  {
    name: "Zimbo88",
    url: "https://github.com/Zimbo88",
    contribution: "Reverse engineering, factory-reset fix, persistence initialization",
  },
  {
    name: "danielkohl",
    url: "https://github.com/danielkohl",
    contribution: "Root cause discovery (HTTPS→HTTP protocol fix), first working manual fix",
  },
  {
    name: "ubittner",
    url: "https://github.com/ubittner",
    contribution: "margeAccountUUID correlation analysis, systematic debugging",
  },
  {
    name: "bratwurstbraeter",
    url: "https://github.com/bratwurstbraeter",
    contribution: "Bosman app discovery that enabled the factory-reset fix",
  },
];

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

        <hr className="about-divider" />

        {/* Community contributors */}
        <h3 className="about-credits-title">
          <span className="about-meta-icon">{"\uD83C\uDFC6"}</span>
          {t("about.creditsTitle")}
        </h3>
        <p className="about-credits-description">{t("about.creditsDescription")}</p>
        <ul className="about-links">
          {CONTRIBUTORS.map((c) => (
            <li key={c.name}>
              <a href={c.url} target="_blank" rel="noopener noreferrer" className="about-link-item">
                <span className="about-link-icon">{"\uD83D\uDC64"}</span>
                <span className="about-link-label">
                  <strong>@{c.name}</strong>
                  <span className="about-contributor-detail"> — {c.contribution}</span>
                </span>
                <span className="about-link-chevron">{"\u203A"}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </motion.section>
  );
}

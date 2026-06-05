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

// 🏛️ Hall of Fame — Top 3 contributors of all time (by qualitative impact)
const HALL_OF_FAME = [
  {
    name: "Zimbo88",
    url: "https://github.com/Zimbo88",
    contribution: "Reverse engineering, USB-less provisioning research, v5 patch evaluation",
  },
  {
    name: "BullHurley",
    url: "https://github.com/BullHurley",
    contribution: "Critical audio failure debugging (#184, #166)",
  },
  {
    name: "reinhard-evvc",
    url: "https://github.com/reinhard-evvc",
    contribution: "Extensive preset persistence diagnostics (#167)",
  },
];

// 💰 Supporters — Financial supporters (update manually)
// Sorted by contribution amount (descending)
const SUPPORTERS = {
  monthly: [
    // { name: "Username", amount: 10 },
  ] as Array<{ name: string; amount: number }>,
  oneTime: [
    // { name: "Username", amount: 50 },
  ] as Array<{ name: string; amount: number }>,
};

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

        {/* 🏛️ Hall of Fame */}
        <h3 className="about-credits-title">
          <span className="about-meta-icon">{"\uD83C\uDFDB\uFE0F"}</span>
          {t("about.hallOfFameTitle")}
        </h3>
        <p className="about-credits-description">{t("about.hallOfFameDescription")}</p>
        <ul className="about-links">
          {HALL_OF_FAME.map((c) => (
            <li key={c.name}>
              <a href={c.url} target="_blank" rel="noopener noreferrer" className="about-link-item">
                <span className="about-link-icon">{"\uD83C\uDFC6"}</span>
                <span className="about-link-label">
                  <strong>@{c.name}</strong>
                  <span className="about-contributor-detail"> — {c.contribution}</span>
                </span>
                <span className="about-link-chevron">{"\u203A"}</span>
              </a>
            </li>
          ))}
        </ul>

        {/* 💛 Supporters (only show if not empty) */}
        {(SUPPORTERS.monthly.length > 0 || SUPPORTERS.oneTime.length > 0) && (
          <>
            <hr className="about-divider" />
            <h3 className="about-credits-title">
              <span className="about-meta-icon">{"\uD83D\uDC9B"}</span>
              {t("about.supportersTitle")}
            </h3>
            <p className="about-credits-description">{t("about.supportersDescription")}</p>

            {SUPPORTERS.monthly.length > 0 && (
              <div className="about-supporters-section">
                <h4 className="about-supporters-subtitle">{t("about.supportersMonthly")}</h4>
                <ul className="about-supporters-list">
                  {SUPPORTERS.monthly.map((s) => (
                    <li key={s.name} className="about-supporter-item">
                      {"\u2615"} <strong>{s.name}</strong>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {SUPPORTERS.oneTime.length > 0 && (
              <div className="about-supporters-section">
                <h4 className="about-supporters-subtitle">{t("about.supportersOneTime")}</h4>
                <ul className="about-supporters-list">
                  {SUPPORTERS.oneTime.map((s) => (
                    <li key={s.name} className="about-supporter-item">
                      {"\uD83C\uDF89"} <strong>{s.name}</strong>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </motion.section>
  );
}

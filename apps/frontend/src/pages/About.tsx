import { useTranslation, Trans } from "react-i18next";
import { useState, useEffect, useMemo, type CSSProperties } from "react";
import { Link } from "react-router";
import { useHealth } from "../hooks/useHealth";
import { Skeleton } from "../components/LoadingSkeleton";
import { Icon } from "../components/Icon";
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

/** Marks a link that opens a new tab: icon for the eye, text for assistive technology. */
function NewTabHint() {
  const { t } = useTranslation();
  return (
    <>
      <span className="ab-ext" aria-hidden="true">
        {Icon.ExternalLink(16)}
      </span>
      <span className="visually-hidden">{t("about.externalLink")}</span>
    </>
  );
}

export default function About() {
  const { t, i18n } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealth();
  const startTime = useMemo(
    () => (health?.uptime ? new Date(Date.now() - health.uptime * 1000).toLocaleString() : ""),
    [health?.uptime]
  );

  const [supporters, setSupporters] = useState<Supporter[]>([]);
  const [supportersLoading, setSupportersLoading] = useState(true);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [updateLoading, setUpdateLoading] = useState(true);
  // one thank-you sentence per visit instead of a tooltip on every name
  const thanks = useMemo(() => getRandomThankYou(false, i18n.language), [i18n.language]);

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
          .map(
            ([
              name = "",
              type = "one-time",
              amount = "",
              monthlyAmount = "",
              firstSupportDate = "",
            ]) => ({
              name,
              type: type as "monthly" | "one-time",
              amount: Number.parseFloat(amount) || 0,
              monthlyAmount: Number.parseFloat(monthlyAmount) || 0,
              firstSupportDate,
            })
          );

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

      if (health.build !== "official") {
        setUpdateInfo({ available: false });
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
    return undefined;
  }, [health?.version, health?.build]);

  const maxAmount = Math.max(...supporters.map((s) => s.amount + s.monthlyAmount), 1);

  return (
    <div className="ab">
      {/* Header */}
      <header className="ab-header">
        <img
          className="ab-logo"
          src="/images/logo/oct-logo-dark_539x539.png"
          alt=""
          width={96}
          height={96}
        />
        <h1 className="ab-title">OpenCloudTouch</h1>
        <div className="ab-version-slot">
          {healthLoading && <Skeleton width="60px" height="24px" borderRadius="20px" />}
          {!healthLoading && health && (
            <span className="ui-badge ui-badge--info ui-badge--large">v{health.version}</span>
          )}
        </div>
        {/* stays optional; /health sends no uptime yet (#521), so nothing is rendered today */}
        {!healthLoading && health?.uptime && (
          <p className="ui-small ab-build-time">{t("about.buildTime", { time: startTime })}</p>
        )}
      </header>

      {/* Update Check: the slot is always there, so the result is announced and the page does not jump */}
      <div className="ab-update" aria-live="polite">
        {updateLoading && (
          <div className="wz-status ab-status">
            <span className="wz-icon">
              <span className="spinner-small" aria-hidden="true" />
            </span>
            <div className="wz-status-body">
              <p>{t("about.checkingUpdates")}</p>
            </div>
          </div>
        )}
        {!updateLoading && updateInfo.available && (
          <div className="wz-status ab-status">
            <span className="wz-icon" aria-hidden="true">
              {Icon.Sparkles(22)}
            </span>
            <div className="wz-status-body ab-update-body">
              <p>{t("about.updateAvailable", { version: updateInfo.latestVersion })}</p>
              <a
                href={updateInfo.releaseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primary btn-sm"
              >
                {t("about.viewRelease")}
                <NewTabHint />
              </a>
            </div>
          </div>
        )}
        {!updateLoading && !updateInfo.available && health && health.build !== "official" && (
          <div className="wz-status ab-status">
            <span className="wz-icon" aria-hidden="true">
              {Icon.Wrench(22)}
            </span>
            <div className="wz-status-body">
              <p>{t("about.devBuild")}</p>
            </div>
          </div>
        )}
        {!updateLoading && !updateInfo.available && health?.build === "official" && (
          <div className="wz-status wz-status--success ab-status">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleCheck(22)}
            </span>
            <div className="wz-status-body">
              <p>{t("about.upToDate")}</p>
            </div>
          </div>
        )}
      </div>

      {/* Supporters Wimmelbild */}
      {!supportersLoading && supporters.length > 0 && (
        <section className="ab-supporters" aria-labelledby="ab-supporters-title">
          <h2 id="ab-supporters-title" className="ui-h2" aria-label={t("about.supportersLabel")}>
            <Trans
              i18nKey="about.supportersTitle"
              components={[
                <span className="ab-heart" aria-hidden="true" key="heart">
                  {Icon.Heart(22)}
                </span>,
              ]}
            />
          </h2>
          <p className="ui-small ab-thanks">{thanks}</p>
          <ul className="ui-card ab-cloud">
            {supporters.map((supporter, index) => {
              const fontSize = getFontSize(supporter, maxAmount);
              const color = generateGradientColor(index, supporters.length);
              const isMonthly = supporter.monthlyAmount > 0;
              const supporterKey = `${supporter.name}-${index}`;

              return (
                <li
                  key={supporterKey}
                  className={isMonthly ? "ab-name ab-name--monthly" : "ab-name"}
                  style={
                    {
                      fontSize: `${fontSize}px`,
                      color: isMonthly ? undefined : color,
                      "--i": Math.min(index, 40),
                    } as CSSProperties
                  }
                >
                  {cleanName(supporter.name)}
                  {isMonthly && <span className="visually-hidden"> {t("about.monthlySupporter")}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* Links */}
      <nav className="ab-links" aria-label={t("about.linksLabel")}>
        <ul>
          <li>
            <a
              href={`https://github.com/${GITHUB_REPO}`}
              target="_blank"
              rel="noopener noreferrer"
              className="ab-link"
            >
              <span className="ab-link-icon" aria-hidden="true">
                {Icon.Github(22)}
              </span>
              <span className="ab-link-label">{t("about.github")}</span>
              <NewTabHint />
            </a>
          </li>
          <li>
            <a
              href={`https://github.com/${GITHUB_REPO}/issues/new?template=bug_report.yml`}
              target="_blank"
              rel="noopener noreferrer"
              className="ab-link"
            >
              <span className="ab-link-icon" aria-hidden="true">
                {Icon.Bug(22)}
              </span>
              <span className="ab-link-label">{t("about.reportBug")}</span>
              <NewTabHint />
            </a>
          </li>
          <li>
            <Link to="/diagnostics" className="ab-link">
              <span className="ab-link-icon" aria-hidden="true">
                {Icon.Wrench(22)}
              </span>
              <span className="ab-link-label">{t("about.diagnostics")}</span>
              <span className="ab-ext" aria-hidden="true">
                {Icon.ChevronRight(18)}
              </span>
            </Link>
          </li>
          {/* the Licenses page was only reachable by URL */}
          <li>
            <Link to="/licenses" className="ab-link">
              <span className="ab-link-icon" aria-hidden="true">
                {Icon.FileText(22)}
              </span>
              <span className="ab-link-label">{t("about.licenses")}</span>
              <span className="ab-ext" aria-hidden="true">
                {Icon.ChevronRight(18)}
              </span>
            </Link>
          </li>
          <li>
            <a
              href={BMC_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="ab-link ab-link--support"
            >
              <span className="ab-link-icon" aria-hidden="true">
                {Icon.Coffee(22)}
              </span>
              <span className="ab-link-label">{t("about.support")}</span>
              <NewTabHint />
            </a>
          </li>
        </ul>
      </nav>
    </div>
  );
}

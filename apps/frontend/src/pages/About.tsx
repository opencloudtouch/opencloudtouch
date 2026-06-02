import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useState, useEffect, useRef } from "react";
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
}

// Thank you phrases per language
const THANK_YOU_PHRASES = {
  regular: {
    en: [
      "Thank you for your support! ☕",
      "You make the difference! 🎵",
      "Thanks a lot! 💙",
      "Super cool of you! 🚀",
      "You rock! 🎸",
      "Thanks for being here! 🙌",
      "You're awesome! ⭐",
      "Heartfelt thanks! ❤️",
      "You help us forward! 🌟",
      "Thanks for your support! 💪",
      "You're the hammer! 🔨",
      "Many thanks! 🎉",
      "You're great! 🌈",
      "Thanks for joining! 🤝",
      "You're a hero! 🦸",
      "Thanks for the coffee! ☕",
      "You're fantastic! 👏",
      "Many thanks! 🎁",
      "You make it possible! ✨",
      "Thanks, you legend! 🏆",
    ],
    de: [
      "Danke für deine Unterstützung! ☕",
      "Du machst den Unterschied! 🎵",
      "Vielen Dank! 💙",
      "Mega cool von dir! 🚀",
      "Du rockst! 🎸",
      "Danke, dass du dabei bist! 🙌",
      "Du bist awesome! ⭐",
      "Herzlichen Dank! ❤️",
      "Du hilfst uns weiter! 🌟",
      "Danke für deinen Support! 💪",
      "Du bist der Hammer! 🔨",
      "Vielen lieben Dank! 🎉",
      "Du bist großartig! 🌈",
      "Danke fürs Mitmachen! 🤝",
      "Du bist ein Held! 🦸",
      "Danke für den Kaffee! ☕",
      "Du bist klasse! 👏",
      "Vielen Dank dafür! 🎁",
      "Du machst's möglich! ✨",
      "Danke, du Ehrenmensch! 🏆",
    ],
  },
  monthly: {
    en: [
      "You're a champion! 🏆💛",
      "Thanks for your loyal support! ✨",
      "You're worth gold! 💰",
      "Wow, thanks for the monthly commitment! 🌟",
      "You're absolutely amazing! 🚀",
      "Thanks for being here every month! 💙",
      "You're a superhero! 🦸‍♂️",
      "Many thanks for your loyalty! 🙏",
      "You make the project possible! 🎉",
      "Thanks for your continuous help! 💪",
      "You're simply fantastic! ⭐",
      "Heartfelt thanks for your loyalty! ❤️",
      "You're priceless! 💎",
      "Thanks for the monthly fuel! ⚡",
      "You're a rockstar! 🎸",
    ],
    de: [
      "Du bist ein Champion! 🏆💛",
      "Danke für deine treue Unterstützung! ✨",
      "Du bist Gold wert! 💰",
      "Wow, danke fürs monatliche Commitment! 🌟",
      "Du bist der absolute Wahnsinn! 🚀",
      "Danke, dass du jeden Monat dabei bist! 💙",
      "Du bist ein Superheld! 🦸‍♂️",
      "Vielen Dank für deine Treue! 🙏",
      "Du machst das Projekt möglich! 🎉",
      "Danke für deine kontinuierliche Hilfe! 💪",
      "Du bist einfach fantastisch! ⭐",
      "Herzlichen Dank für deine Loyalität! ❤️",
      "Du bist unbezahlbar! 💎",
      "Danke fürs monatliche Fuel! ⚡",
      "Du bist ein Rockstar! 🎸",
    ],
  },
};

export default function About() {
  const { t, i18n } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealth();

  const [supporters, setSupporters] = useState<Supporter[]>([]);
  const [supportersLoading, setSupportersLoading] = useState(true);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [updateLoading, setUpdateLoading] = useState(true);
  const tooltipRefs = useRef<Map<string, string>>(new Map());

  // Get random thank you phrase
  const getRandomThankYou = (isMonthly: boolean) => {
    const currentLang = i18n.language.split("-")[0]; // en-US → en
    const fallbackLang = "en";

    const category = isMonthly ? "monthly" : "regular";
    const phrases =
      THANK_YOU_PHRASES[category][currentLang as keyof typeof THANK_YOU_PHRASES.regular] ||
      THANK_YOU_PHRASES[category][fallbackLang];

    return phrases[Math.floor(Math.random() * phrases.length)];
  };

  // Load supporters from CSV
  useEffect(() => {
    const loadSupporters = async () => {
      try {
        const response = await fetch("/supporters.csv");
        if (!response.ok) {
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

        // Sort by total support: amount + monthlyAmount DESC
        parsed.sort((a, b) => {
          const scoreA = a.amount + a.monthlyAmount;
          const scoreB = b.amount + b.monthlyAmount;
          if (scoreB !== scoreA) return scoreB - scoreA;
          if (a.firstSupportDate !== b.firstSupportDate) {
            return a.firstSupportDate.localeCompare(b.firstSupportDate);
          }
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

  // Calculate font size based on support amount
  const getFontSize = (supporter: Supporter, maxAmount: number) => {
    const totalSupport = supporter.amount + supporter.monthlyAmount;
    const ratio = totalSupport / maxAmount;
    const minSize = 12;
    const maxSize = 32;
    return Math.floor(minSize + (maxSize - minSize) * ratio);
  };

  // Generate smooth color gradient
  const generateGradientColor = (index: number, total: number) => {
    const hue = (index / total) * 360;
    const saturation = 60 + (index % 3) * 10;
    const lightness = 55 + (index % 2) * 10;
    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  };

  // Clean GitHub URLs
  const cleanName = (name: string) => {
    if (name.startsWith("https://github.com/")) {
      return "@" + name.replace("https://github.com/", "");
    }
    return name;
  };

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

                // Get or create tooltip for this supporter
                if (!tooltipRefs.current.has(supporterKey)) {
                  tooltipRefs.current.set(supporterKey, getRandomThankYou(isMonthly));
                }

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
                    title={tooltipRefs.current.get(supporterKey)}
                    onMouseEnter={() => {
                      // Generate new random phrase on hover
                      tooltipRefs.current.set(supporterKey, getRandomThankYou(isMonthly));
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

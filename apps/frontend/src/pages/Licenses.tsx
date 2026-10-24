import { useId } from "react";
import { useTranslation, Trans } from "react-i18next";
import { Icon } from "../components/Icon";
import "./Licenses.css";

/**
 * Licenses Component
 *
 * Displays all external libraries and their licenses.
 * Ensures open-source compliance.
 */

interface Dependency {
  name: string;
  version: string;
  license: string;
  url: string;
}

interface Dependencies {
  frontend: Dependency[];
  backend: Dependency[];
  build: Dependency[];
}

const REPO_URL = "https://github.com/opencloudtouch/opencloudtouch";

// Data unchanged (outdated versions are tracked in issue #526).
const DEPENDENCIES: Dependencies = {
  frontend: [
    { name: "React", version: "18.2.0", license: "MIT", url: "https://reactjs.org" },
    { name: "React Router", version: "6.20.0", license: "MIT", url: "https://reactrouter.com" },
    {
      name: "Framer Motion",
      version: "10.16.16",
      license: "MIT",
      url: "https://www.framer.com/motion",
    },
  ],
  backend: [
    { name: "FastAPI", version: "0.100+", license: "MIT", url: "https://fastapi.tiangolo.com" },
    { name: "uvicorn", version: "latest", license: "BSD-3-Clause", url: "https://www.uvicorn.org" },
    {
      name: "httpx",
      version: "latest",
      license: "BSD-3-Clause",
      url: "https://www.python-httpx.org",
    },
    {
      name: "aiosqlite",
      version: "latest",
      license: "MIT",
      url: "https://github.com/omnilib/aiosqlite",
    },
    { name: "pydantic", version: "2.0+", license: "MIT", url: "https://docs.pydantic.dev" },
    {
      name: "libsoundtouch",
      version: "latest",
      license: "Apache-2.0",
      url: "https://github.com/CharlesBlonde/libsoundtouch",
    },
  ],
  build: [
    { name: "Vite", version: "5.0.8", license: "MIT", url: "https://vitejs.dev" },
    { name: "pytest", version: "latest", license: "MIT", url: "https://pytest.org" },
    { name: "Docker", version: "latest", license: "Apache-2.0", url: "https://www.docker.com" },
  ],
};

function LicenseGroup({
  title,
  items,
}: Readonly<{
  title: string;
  items: Dependency[];
}>) {
  const { t } = useTranslation();
  const titleId = useId();
  return (
    <section className="lic-group" aria-labelledby={titleId}>
      <h2 id={titleId} className="ui-h2">
        {title}
      </h2>
      <ul className="ui-card lic-list">
        {items.map((dep) => (
          <li key={dep.name} className="lic-item">
            <a
              className="lic-name"
              href={dep.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${t("about.libraryWebsite", { name: dep.name })} ${t("about.externalLink")}`}
            >
              <span>{dep.name}</span>
              <span className="lic-ext" aria-hidden="true">
                {Icon.ExternalLink(14)}
              </span>
            </a>
            <span className="lic-version">
              <span className="lic-k">{t("about.licensesVersion")}</span>{" "}
              <span className="ui-mono">{dep.version}</span>
            </span>
            <span className="ui-badge lic-badge">{dep.license}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Licenses() {
  const { t } = useTranslation();

  return (
    <div className="lic">
      <header className="lic-header">
        <h1 className="ui-h1">{t("about.licensesTitle")}</h1>
        <p className="lic-text">{t("about.licensesDescription")}</p>
      </header>

      <LicenseGroup title={t("about.licensesGroup.frontend")} items={DEPENDENCIES.frontend} />
      <LicenseGroup title={t("about.licensesGroup.backend")} items={DEPENDENCIES.backend} />
      <LicenseGroup title={t("about.licensesGroup.build")} items={DEPENDENCIES.build} />

      {/* Footer notices: h2 (not h3) so the heading order stays h1 > h2 */}
      <section className="ui-card lic-note" aria-labelledby="lic-compliance-title">
        <h2 id="lic-compliance-title" className="ui-h3">
          {t("about.licenseCompliance")}
        </h2>
        <p className="lic-text">{t("about.licenseComplianceText")}</p>
        <p className="lic-text">
          <strong>{t("about.licenseProject")}:</strong>{" "}
          <a
            className="lic-link"
            href={`${REPO_URL}/blob/main/LICENSE`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("about.licenseApache")}
            <span className="visually-hidden"> {t("about.externalLink")}</span>
          </a>
        </p>
      </section>

      <section
        className="wz-status wz-status--warning lic-trademark"
        aria-labelledby="lic-trademark-title"
      >
        <span className="wz-icon" aria-hidden="true">
          {Icon.Alert(22)}
        </span>
        <div className="wz-status-body">
          <h2 id="lic-trademark-title" className="ui-h3">
            {t("about.trademarkTitle")}
          </h2>
          <p>
            <Trans i18nKey="about.trademarkText1" components={[<strong key="b" />]} />
          </p>
          <p>
            <Trans
              i18nKey="about.trademarkText2"
              components={[
                <a
                  className="lic-link"
                  key="l"
                  href={`${REPO_URL}/blob/main/TRADEMARK.md`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  TRADEMARK.md
                </a>,
              ]}
            />
          </p>
        </div>
      </section>

      <section className="lic-note lic-attribution" aria-labelledby="lic-about-title">
        <h2 id="lic-about-title" className="ui-h3">
          {t("about.sectionTitle")}
        </h2>
        <p className="lic-text">{t("about.appDescription")}</p>
      </section>
    </div>
  );
}

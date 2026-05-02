import { useTranslation } from "react-i18next";
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

export default function Licenses() {
  const { t } = useTranslation();
  const dependencies: Dependencies = {
    frontend: [
      {
        name: "React",
        version: "18.2.0",
        license: "MIT",
        url: "https://reactjs.org",
      },
      {
        name: "React Router",
        version: "6.20.0",
        license: "MIT",
        url: "https://reactrouter.com",
      },
      {
        name: "Framer Motion",
        version: "10.16.16",
        license: "MIT",
        url: "https://www.framer.com/motion",
      },
    ],
    backend: [
      {
        name: "FastAPI",
        version: "0.100+",
        license: "MIT",
        url: "https://fastapi.tiangolo.com",
      },
      {
        name: "uvicorn",
        version: "latest",
        license: "BSD-3-Clause",
        url: "https://www.uvicorn.org",
      },
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
      {
        name: "pydantic",
        version: "2.0+",
        license: "MIT",
        url: "https://docs.pydantic.dev",
      },
      {
        name: "libsoundtouch",
        version: "latest",
        license: "Apache-2.0",
        url: "https://github.com/CharlesBlonde/libsoundtouch",
      },
    ],
    build: [
      {
        name: "Vite",
        version: "5.0.8",
        license: "MIT",
        url: "https://vitejs.dev",
      },
      {
        name: "pytest",
        version: "latest",
        license: "MIT",
        url: "https://pytest.org",
      },
      {
        name: "Docker",
        version: "latest",
        license: "Apache-2.0",
        url: "https://www.docker.com",
      },
    ],
  };

  const renderLicenseTable = (title: string, items: Dependency[]) => (
    <div className="license-section">
      <h2>{title}</h2>
      <div className="license-table">
        <div className="license-header">
          <div>Bibliothek</div>
          <div>Version</div>
          <div>Lizenz</div>
          <div>Link</div>
        </div>
        {items.map((dep) => (
          <div key={dep.name} className="license-row">
            <div className="lib-name">{dep.name}</div>
            <div className="lib-version">{dep.version}</div>
            <div className="lib-license">
              <span className="license-badge">{dep.license}</span>
            </div>
            <div className="lib-link">
              <a href={dep.url} target="_blank" rel="noopener noreferrer">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M13 3L6 10M13 3H8M13 3V8"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M11 13H3V5H6"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="licenses-page">
      <div className="licenses-header">
        <h1>{t("about.licensesTitle")}</h1>
        <p>{t("about.licensesDescription")}</p>
      </div>

      <div className="licenses-content">
        {renderLicenseTable("Frontend", dependencies.frontend)}
        {renderLicenseTable("Backend", dependencies.backend)}
        {renderLicenseTable("Build Tools", dependencies.build)}
      </div>

      <div className="licenses-footer">
        <div className="compliance-notice">
          <h3>{t("about.licenseCompliance")}</h3>
          <p>{t("about.licenseComplianceText")}</p>
          <p>
            <strong>OpenCloudTouch Lizenz:</strong>{" "}
            <a
              href="https://github.com/yourusername/opencloudtouch/blob/main/LICENSE"
              target="_blank"
              rel="noopener noreferrer"
            >
              Apache License 2.0
            </a>
          </p>
        </div>

        <div className="trademark-notice">
          <h3>⚠️ Trademark Notice</h3>
          <p>
            OpenCloudTouch is <strong>not affiliated with Bose Corporation</strong>. Bose® and
            SoundTouch® are registered trademarks of Bose Corporation.
          </p>
          <p>
            This software interfaces with Bose SoundTouch® devices using their publicly documented
            local APIs. See{" "}
            <a
              href="https://github.com/yourusername/opencloudtouch/blob/main/TRADEMARK.md"
              target="_blank"
              rel="noopener noreferrer"
            >
              TRADEMARK.md
            </a>{" "}
            for details.
          </p>
        </div>

        <div className="attribution">
          <h3>{t("about.sectionTitle")}</h3>
          <p>{t("about.appDescription")}</p>
        </div>
      </div>
    </div>
  );
}

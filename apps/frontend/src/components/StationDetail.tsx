import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../api/types";
import { Icon } from "./Icon";
import "./StationDetail.css";

export interface StationDetailData {
  uuid: string;
  name: string;
  url: string;
  homepage: string | null;
  favicon: string | null;
  tags: string[] | null;
  country: string;
  codec: string | null;
  bitrate: number | null;
  provider: string;
}

interface StationDetailProps {
  stationUuid: string;
  provider?: string;
  onBack: () => void;
  onSelect: (station: StationDetailData) => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const cypress = (window as { Cypress?: { expose?: (key: string) => unknown } }).Cypress;
    const apiUrl = cypress?.expose?.("apiUrl");
    if (typeof apiUrl === "string" && apiUrl.length > 0) {
      return apiUrl.replace(/\/api\/?$/, "");
    }
  }
  return API_BASE_URL;
}

export default function StationDetail({
  stationUuid,
  provider,
  onBack,
  onSelect,
}: StationDetailProps) {
  const { t } = useTranslation();
  const [station, setStation] = useState<StationDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchDetail() {
      setLoading(true);
      setError(null);
      try {
        const baseUrl = getApiBaseUrl();
        const providerParam = provider ? `?provider=${provider}` : "";
        const res = await fetch(
          `${baseUrl}/api/radio/station/${encodeURIComponent(stationUuid)}${providerParam}`,
          {
            signal: controller.signal,
          }
        );
        if (!res.ok) {
          setError(t("errors.loadFailed"));
          return;
        }
        const data: StationDetailData = await res.json();
        setStation(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    fetchDetail();
    return () => controller.abort();
  }, [stationUuid, provider, t]);

  if (loading) {
    return (
      <div className="sd">
        <output className="sd-loading">
          <span className="spinner" aria-hidden="true" />
          {t("common.loading")}
        </output>
      </div>
    );
  }

  if (error || !station) {
    return (
      <div className="sd">
        <div className="sd-body">
          <div className="wz-status wz-status--error" role="alert">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleX(20)}
            </span>
            <div className="wz-status-body">
              <p className="sd-error">{error || t("common.stationNotFound")}</p>
            </div>
          </div>
        </div>
        <div className="sd-actions">
          <button className="btn btn-secondary" onClick={onBack}>
            {Icon.ArrowLeft(18)} {t("common.back")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="sd">
      <section
        className="sd-body"
        tabIndex={0} // NOSONAR(S6845): scrollable region must be keyboard-focusable (WCAG 2.1.1)
        aria-label={station.name}
      >
        <div className="sd-header">
          {station.favicon && (
            <img
              className="sd-favicon"
              src={station.favicon}
              alt=""
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div className="sd-title">
            <h3 className="sd-name">{station.name}</h3>
            <span className="sd-country">{station.country}</span>
          </div>
        </div>

        <dl className="sd-meta">
          {station.codec && (
            <div className="sd-meta-item">
              <dt className="sd-label">{t("stationDetail.codec")}</dt>
              <dd className="sd-value">{station.codec}</dd>
            </div>
          )}
          {station.bitrate != null && station.bitrate > 0 && (
            <div className="sd-meta-item">
              <dt className="sd-label">{t("stationDetail.bitrate")}</dt>
              <dd className="sd-value">{station.bitrate} kbps</dd>
            </div>
          )}
          {station.homepage && (
            <div className="sd-meta-item">
              <dt className="sd-label">{t("stationDetail.homepage")}</dt>
              <dd className="sd-value">
                <a
                  className="sd-link"
                  href={station.homepage}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {new URL(station.homepage).hostname}
                  {Icon.ExternalLink(14)}
                </a>
              </dd>
            </div>
          )}
        </dl>

        {station.tags && station.tags.length > 0 && (
          <ul className="sd-tags">
            {station.tags.map((tag) => (
              <li key={tag} className="ui-badge sd-tag">
                {tag}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="sd-actions">
        <button className="btn btn-secondary" onClick={onBack}>
          {Icon.ArrowLeft(18)} {t("common.back")}
        </button>
        <button className="btn btn-primary" onClick={() => onSelect(station)}>
          {t("common.saveAsPreset")}
        </button>
      </div>
    </div>
  );
}

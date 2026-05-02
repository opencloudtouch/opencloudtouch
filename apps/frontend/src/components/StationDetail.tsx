import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../api/types";
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
          setError("Station konnte nicht geladen werden.");
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
  }, [stationUuid, provider]);

  if (loading) {
    return (
      <div className="station-detail">
        <div className="sd-loading">Lade Details…</div>
      </div>
    );
  }

  if (error || !station) {
    return (
      <div className="station-detail">
        <div className="sd-error">{error || t("common.stationNotFound")}</div>
        <button className="sd-back" onClick={onBack}>
          ← {t("common.back")}
        </button>
      </div>
    );
  }

  return (
    <div className="station-detail">
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

      <div className="sd-meta">
        {station.codec && (
          <div className="sd-meta-item">
            <span className="sd-label">Codec</span>
            <span className="sd-value">{station.codec}</span>
          </div>
        )}
        {station.bitrate != null && station.bitrate > 0 && (
          <div className="sd-meta-item">
            <span className="sd-label">Bitrate</span>
            <span className="sd-value">{station.bitrate} kbps</span>
          </div>
        )}
        {station.homepage && (
          <div className="sd-meta-item">
            <span className="sd-label">Homepage</span>
            <a
              className="sd-link"
              href={station.homepage}
              target="_blank"
              rel="noopener noreferrer"
            >
              {new URL(station.homepage).hostname}
            </a>
          </div>
        )}
      </div>

      {station.tags && station.tags.length > 0 && (
        <div className="sd-tags">
          {station.tags.map((tag) => (
            <span key={tag} className="sd-tag">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="sd-actions">
        <button className="sd-back" onClick={onBack}>
          ← {t("common.back")}
        </button>
        <button className="sd-select" onClick={() => onSelect(station)}>
          {t("common.saveAsPreset")}
        </button>
      </div>
    </div>
  );
}

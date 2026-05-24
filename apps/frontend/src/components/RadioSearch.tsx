import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { HAS_TUNEIN_SUPPORT } from "../config/capabilities";
import { getErrorMessage, parseApiError } from "../api/types";
import { getAvatarColor, getStationInitials } from "../utils/stationAvatar";
import StationDetail from "./StationDetail";
import "./RadioSearch.css";

export interface RadioStation {
  stationuuid: string;
  name: string;
  country: string;
  url?: string;
  homepage?: string;
  favicon?: string;
  // Add other station properties as needed
}

interface RawStationData {
  uuid: string;
  name: string;
  country: string;
  url?: string;
  homepage?: string;
  favicon?: string;
}

interface RadioSearchProps {
  onStationSelect: (station: RadioStation) => void | Promise<void>;
  isOpen: boolean;
  onClose?: () => void;
  onDelete?: () => void | Promise<void>;
  presetNumber?: number | null;
  hasExistingPreset?: boolean;
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

type SearchType = "name" | "country" | "tag";
type RadioProviderType = "radiobrowser" | "tunein";

const SEARCH_TYPES: { value: SearchType }[] = [
  { value: "name" },
  { value: "country" },
  { value: "tag" },
];

const ALL_PROVIDERS: { value: RadioProviderType; label: string }[] = [
  { value: "tunein", label: "TuneIn" },
  { value: "radiobrowser", label: "RadioBrowser" },
];

const PROVIDERS = HAS_TUNEIN_SUPPORT
  ? ALL_PROVIDERS
  : ALL_PROVIDERS.filter((p) => p.value !== "tunein");

export default function RadioSearch({
  onStationSelect,
  isOpen,
  onClose,
  onDelete,
  presetNumber: _presetNumber,
  hasExistingPreset,
}: RadioSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RadioStation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<SearchType>("name");
  const [radioProvider, setRadioProvider] = useState<RadioProviderType>(
    HAS_TUNEIN_SUPPORT ? "tunein" : "radiobrowser"
  );
  const [detailUuid, setDetailUuid] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery);
    setError(null);
    if (!searchQuery.trim()) {
      setResults([]);
      setLoading(false);
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
      }
      if (abortRef.current) {
        abortRef.current.abort();
      }
      return;
    }

    if (searchQuery.trim().length < 2) {
      setResults([]);
      setLoading(false);
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
      }
      if (abortRef.current) {
        abortRef.current.abort();
      }
      return;
    }

    setLoading(true);
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
    }
    if (abortRef.current) {
      abortRef.current.abort();
    }

    debounceRef.current = window.setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const baseUrl = getApiBaseUrl();
        const response = await fetch(
          `${baseUrl}/api/radio/search?q=${encodeURIComponent(searchQuery)}&search_type=${searchType}&limit=10&provider=${radioProvider}`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          // Parse standardized error response (RFC 7807)
          const apiError = await parseApiError(response);
          console.error("Radio search failed:", apiError || response);

          // Use user-friendly error message from getErrorMessage
          if (apiError) {
            setError(getErrorMessage(apiError));
          } else {
            setError(t("presets.searchFailed"));
          }
          setResults([]);
          return;
        }

        const data = await response.json();
        const stations = Array.isArray(data?.stations) ? data.stations : [];
        const normalized: RadioStation[] = stations.map((station: RawStationData) => ({
          stationuuid: station.uuid,
          name: station.name,
          country: station.country,
          url: station.url,
          homepage: station.homepage,
          favicon: station.favicon,
        }));

        setResults(normalized);
        setError(null);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setResults([]);
        setError(getErrorMessage(err));
        console.error("Radio search error:", err);
      } finally {
        setLoading(false);
      }
    }, 500);
  };

  const handleSelect = async (station: RadioStation) => {
    await onStationSelect(station);
    setQuery("");
    setResults([]);
    setDetailUuid(null);
    onClose?.();
  };

  if (!isOpen) return null;

  return (
    <div
      className="radio-search-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose?.();
      }}
      tabIndex={-1}
      role="none"
    >
      <div
        className="radio-search-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("presets.searchTitle")}
      >
        {detailUuid ? (
          <StationDetail
            stationUuid={detailUuid}
            provider={radioProvider}
            onBack={() => setDetailUuid(null)}
            onSelect={(s) =>
              handleSelect({
                stationuuid: s.uuid,
                name: s.name,
                country: s.country,
                url: s.url,
                homepage: s.homepage ?? undefined,
                favicon: s.favicon ?? undefined,
              })
            }
          />
        ) : (
          <>
            <div className="search-header">
              <input
                type="search"
                className="search-input"
                placeholder={t(`presets.searchPlaceholder.${searchType}`)}
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
                autoFocus
              />
              <button
                className="search-close"
                onClick={onClose}
                aria-label={t("presets.searchClose")}
                title={t("presets.searchClose")}
              >
                ✕
              </button>
            </div>
            <div className="search-type-row">
              {SEARCH_TYPES.map((st) => (
                <button
                  key={st.value}
                  className={`search-type-chip${searchType === st.value ? " active" : ""}`}
                  onClick={() => {
                    setSearchType(st.value);
                    if (query.trim().length >= 2) handleSearch(query);
                  }}
                >
                  {t(`presets.searchTypeLabel.${st.value}`)}
                </button>
              ))}
            </div>
            {PROVIDERS.length > 1 && (
              <div className="search-type-row">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.value}
                    className={`search-type-chip${radioProvider === p.value ? " active" : ""}`}
                    onClick={() => {
                      setRadioProvider(p.value);
                      if (query.trim().length >= 2) handleSearch(query);
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}

            {hasExistingPreset && onDelete && (
              <div className="search-delete-row">
                <button
                  className="search-delete-btn"
                  onClick={onDelete}
                  aria-label={t("presets.deletePreset")}
                  title={t("presets.deletePreset")}
                >
                  {t("presets.deletePreset")}
                </button>
              </div>
            )}

            <div className="search-results">
              {error && <div className="search-error">{error}</div>}
              {loading && <div className="search-loading">{t("presets.searchLoading")}</div>}
              {!loading && !error && results.length === 0 && query && (
                <div className="search-empty">{t("presets.searchEmpty")}</div>
              )}
              {results.map((station) => (
                <button
                  key={station.stationuuid}
                  className="search-result-item"
                  onClick={() => setDetailUuid(station.stationuuid)}
                >
                  <div className="result-station-logo">
                    {station.favicon ? (
                      <img
                        src={station.favicon}
                        alt=""
                        className="result-favicon"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                          const parent = (e.target as HTMLImageElement).parentElement;
                          if (parent) {
                            const fb = parent.querySelector(
                              ".result-avatar-fallback"
                            ) as HTMLElement;
                            if (fb) fb.style.display = "flex";
                          }
                        }}
                      />
                    ) : null}
                    <span
                      className="result-avatar-fallback"
                      style={{
                        backgroundColor: getAvatarColor(station.name),
                        display: station.favicon ? "none" : "flex",
                      }}
                    >
                      {getStationInitials(station.name)}
                    </span>
                  </div>
                  <div className="result-info">
                    <div className="result-name">{station.name}</div>
                    <div className="result-country">{station.country}</div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

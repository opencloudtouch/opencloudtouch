import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { HAS_TUNEIN_SUPPORT } from "../config/capabilities";
import { getErrorMessage, parseApiError } from "../api/types";
import { getAvatarColor, getStationInitials } from "../utils/stationAvatar";
import StationDetail from "./StationDetail";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";
import { Icon } from "./Icon";
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

interface ExistingPreset {
  station_uuid?: string;
  station_name: string;
  station_url?: string;
  station_favicon?: string;
}

interface RadioSearchProps {
  onStationSelect: (station: RadioStation) => void | Promise<void>;
  isOpen: boolean;
  onClose?: () => void;
  onDelete?: () => void | Promise<void>;
  presetNumber?: number | null;
  hasExistingPreset?: boolean;
  existingPreset?: ExistingPreset | null;
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
type SearchMode = "provider" | "manual";

function isValidHttpUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

const RESULTS_PER_PAGE = 10;
const MAX_RESULTS = 200;

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
  existingPreset,
}: RadioSearchProps) {
  const { t } = useTranslation();
  const [searchMode, setSearchMode] = useState<SearchMode>("provider");
  const [query, setQuery] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualFavicon, setManualFavicon] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [results, setResults] = useState<RadioStation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<SearchType>("name");
  const [radioProvider, setRadioProvider] = useState<RadioProviderType>(
    HAS_TUNEIN_SUPPORT ? "tunein" : "radiobrowser"
  );
  const [detailUuid, setDetailUuid] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const debounceRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const isManualPreset = existingPreset?.station_uuid?.startsWith("manual-") ?? false;

    setQuery("");
    setResults([]);
    setError(null);
    setSaveError(null);
    setDetailUuid(null);
    setOffset(0);
    setHasMore(false);

    if (isManualPreset && existingPreset) {
      setSearchMode("manual");
      setManualUrl(existingPreset.station_url ?? "");
      setManualName(existingPreset.station_name);
      setManualFavicon(existingPreset.station_favicon ?? "");
    } else {
      setSearchMode("provider");
      setManualUrl("");
      setManualName("");
      setManualFavicon("");
    }
  }, [isOpen, existingPreset]);

  const handleSearch = async (
    searchQuery: string,
    provider: RadioProviderType = radioProvider,
    type: SearchType = searchType
  ) => {
    setQuery(searchQuery);
    setError(null);
    setOffset(0);
    setHasMore(false);
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
          `${baseUrl}/api/radio/search?q=${encodeURIComponent(searchQuery)}&search_type=${type}&limit=${RESULTS_PER_PAGE}&offset=0&provider=${provider}`,
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
          setHasMore(false);
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
        setHasMore(data?.has_more === true);
        setError(null);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setResults([]);
        setHasMore(false);
        setError(getErrorMessage(err));
        console.error("Radio search error:", err);
      } finally {
        setLoading(false);
      }
    }, 500);
  };

  const handleLoadMore = async () => {
    const newOffset = offset + RESULTS_PER_PAGE;
    setLoadingMore(true);

    const controller = new AbortController();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(
        `${baseUrl}/api/radio/search?q=${encodeURIComponent(query)}&search_type=${searchType}&limit=${RESULTS_PER_PAGE}&offset=${newOffset}&provider=${radioProvider}`,
        { signal: controller.signal }
      );

      if (!response.ok) {
        const apiError = await parseApiError(response);
        if (apiError) {
          setError(getErrorMessage(apiError));
        } else {
          setError(t("presets.searchFailed"));
        }
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

      setResults((prev) => [...prev, ...normalized]);
      setOffset(newOffset);
      setHasMore(data?.has_more === true);
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setError(getErrorMessage(err));
      console.error("Radio load more error:", err);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleSelect = async (station: RadioStation) => {
    setError(null);
    setSaveError(null);

    try {
      await onStationSelect(station);
      setQuery("");
      setResults([]);
      setDetailUuid(null);
      onClose?.();
    } catch (err) {
      const message = getErrorMessage(err);
      setSaveError(
        message === "Stream URL is not reachable"
          ? t("presets.manualStreamUnreachable")
          : t("presets.manualStreamSaveFailed")
      );
      console.error("Failed to save station:", err);
    }
  };

  const urlInvalid = manualUrl.trim() !== "" && !isValidHttpUrl(manualUrl);
  const faviconInvalid = manualFavicon.trim() !== "" && !isValidHttpUrl(manualFavicon);

  return (
    <Modal open={isOpen} onClose={() => onClose?.()} size="lg" labelledBy="rs-title">
      <ConfirmDialog
        open={saveError !== null}
        title={t("presets.manualStreamErrorTitle")}
        message={saveError ?? ""}
        confirmLabel={t("presets.manualStreamErrorOk")}
        showCancelButton={false}
        onConfirm={() => setSaveError(null)}
        onCancel={() => setSaveError(null)}
      />

      {detailUuid ? (
        <>
          <div className="rs-head rs-head--detail">
            <h2 id="rs-title" className="dlg-title">
              {t("presets.searchTitle")}
            </h2>
            <button
              className="btn btn-ghost btn-icon dlg-close"
              onClick={onClose}
              aria-label={t("presets.searchClose")}
              title={t("presets.searchClose")}
            >
              {Icon.X(22)}
            </button>
          </div>
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
        </>
      ) : (
        <>
          <div className="rs-head">
            <h2 id="rs-title" className="dlg-title">
              {t("presets.searchTitle")}
            </h2>
            {searchMode === "manual" ? (
              <div className="rs-url-field">
                <input
                  type="url"
                  className="ui-input"
                  placeholder={t("presets.manualStreamUrlPlaceholder")}
                  value={manualUrl}
                  onChange={(e) => setManualUrl(e.target.value)}
                  aria-label={t("presets.manualStreamUrlPlaceholder")}
                  data-test="manual-stream-url"
                  aria-describedby={
                    urlInvalid
                      ? "manual-stream-url-help manual-stream-url-error"
                      : "manual-stream-url-help"
                  }
                  aria-invalid={urlInvalid ? true : undefined}
                  data-autofocus
                  autoFocus
                />
              </div>
            ) : (
              <input
                type="search"
                className="ui-input rs-search"
                placeholder={t(`presets.searchPlaceholder.${searchType}`)}
                aria-label={t("presets.searchTitle")}
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
                data-autofocus
                autoFocus
              />
            )}
            <button
              className="btn btn-ghost btn-icon dlg-close rs-close"
              onClick={onClose}
              aria-label={t("presets.searchClose")}
              title={t("presets.searchClose")}
            >
              {Icon.X(22)}
            </button>
          </div>

          {searchMode === "manual" && (
            <div
              className="rs-manual rs-scroll"
              tabIndex={0}
              role="region"
              aria-label={t("presets.manualStreamMode")}
            >
              <div className="ui-field">
                <div id="manual-stream-url-help" className="ui-field-hint">
                  {t("presets.manualStreamUrlHelp")}
                </div>
                {urlInvalid && (
                  <div id="manual-stream-url-error" className="ui-field-error">
                    {Icon.CircleX(16)}
                    <span>{t("presets.manualInvalidUrl")}</span>
                  </div>
                )}
              </div>

              <div className="ui-field">
                <input
                  type="text"
                  className="ui-input"
                  placeholder={t("presets.manualStationNamePlaceholder")}
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  aria-label={t("presets.manualStationNamePlaceholder")}
                  data-test="manual-station-name"
                  aria-describedby="manual-station-name-help"
                />
                <div id="manual-station-name-help" className="ui-field-hint">
                  {t("presets.manualStationNameHelp")}
                </div>
              </div>

              <div className="ui-field">
                <input
                  type="url"
                  className="ui-input"
                  placeholder={t("presets.manualFaviconPlaceholder")}
                  value={manualFavicon}
                  onChange={(e) => setManualFavicon(e.target.value)}
                  aria-label={t("presets.manualFaviconPlaceholder")}
                  data-test="manual-favicon-url"
                  aria-describedby={
                    faviconInvalid
                      ? "manual-favicon-help manual-favicon-error"
                      : "manual-favicon-help"
                  }
                  aria-invalid={faviconInvalid ? true : undefined}
                />
                <div id="manual-favicon-help" className="ui-field-hint">
                  {t("presets.manualFaviconHelp")}
                </div>
                {faviconInvalid && (
                  <div id="manual-favicon-error" className="ui-field-error">
                    {Icon.CircleX(16)}
                    <span>{t("presets.manualInvalidUrl")}</span>
                  </div>
                )}
              </div>
              <button
                className="btn btn-primary btn-block-phone rs-submit"
                disabled={
                  !manualName.trim() ||
                  !isValidHttpUrl(manualUrl) ||
                  (manualFavicon.trim() !== "" && !isValidHttpUrl(manualFavicon))
                }
                onClick={() =>
                  handleSelect({
                    stationuuid: existingPreset?.station_uuid?.startsWith("manual-")
                      ? existingPreset.station_uuid
                      : `manual-${Date.now()}`,
                    name: manualName.trim(),
                    country: "",
                    url: manualUrl.trim(),
                    favicon: manualFavicon.trim() || undefined,
                  })
                }
              >
                {t("presets.manualUseStation")}
              </button>
            </div>
          )}

          <div className="rs-chips">
            <div className="ui-chips" role="group" aria-label={t("presets.searchTypeGroup")}>
              {SEARCH_TYPES.map((st) => (
                <button
                  key={st.value}
                  className="ui-chip"
                  aria-pressed={searchMode === "provider" && searchType === st.value}
                  disabled={searchMode === "manual"}
                  onClick={() => {
                    setSearchType(st.value);
                    if (query.trim().length >= 2) {
                      handleSearch(query, radioProvider, st.value);
                    }
                  }}
                >
                  {t(`presets.searchTypeLabel.${st.value}`)}
                </button>
              ))}
            </div>
            <div className="ui-chips" role="group" aria-label={t("presets.providerGroup")}>
              {PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  className="ui-chip"
                  aria-pressed={searchMode === "provider" && radioProvider === p.value}
                  onClick={() => {
                    setSearchMode("provider");
                    setRadioProvider(p.value);
                    if (query.trim().length >= 2) {
                      handleSearch(query, p.value, searchType);
                    }
                  }}
                >
                  {p.label}
                </button>
              ))}
              <button
                data-test="manual-stream-mode"
                className="ui-chip"
                aria-pressed={searchMode === "manual"}
                onClick={() => {
                  setSearchMode("manual");
                  setQuery("");
                  setResults([]);
                  setError(null);
                  setDetailUuid(null);
                  setOffset(0);
                  setHasMore(false);
                }}
              >
                {t("presets.manualStreamMode")}
              </button>
            </div>
          </div>

          {hasExistingPreset && onDelete && (
            <div className="rs-delete">
              <button
                className="btn btn-danger-outline rs-delete-btn"
                onClick={onDelete}
                aria-label={t("presets.deletePreset")}
                title={t("presets.deletePreset")}
              >
                {Icon.Trash(18)} {t("presets.deletePreset")}
              </button>
            </div>
          )}

          {searchMode === "provider" && (
            <div
              className="rs-results rs-scroll"
              tabIndex={0}
              role="region"
              aria-label={t("presets.searchResults")}
            >
              {error && (
                <div className="wz-status wz-status--error" role="alert">
                  <span className="wz-icon" aria-hidden="true">
                    {Icon.CircleX(20)}
                  </span>
                  <div className="wz-status-body">
                    <p className="search-error">{error}</p>
                  </div>
                </div>
              )}
              {loading && (
                <div className="rs-note" role="status">
                  <span className="spinner-small rs-spinner" aria-hidden="true" />
                  {t("presets.searchLoading")}
                </div>
              )}
              {!loading && !error && results.length === 0 && !query.trim() && (
                <div className="rs-note rs-note--hint">
                  {Icon.Search(20)}
                  <span>{t("presets.searchHint")}</span>
                </div>
              )}
              {!loading && !error && results.length === 0 && query && (
                <div className="rs-note" role="status">
                  {t("presets.searchEmpty")}
                </div>
              )}
              {results.map((station) => (
                <button
                  key={station.stationuuid}
                  className="rs-item"
                  onClick={() => setDetailUuid(station.stationuuid)}
                >
                  <div className="rs-logo">
                    {station.favicon ? (
                      <img
                        src={station.favicon}
                        alt=""
                        className="rs-favicon"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                          const parent = (e.target as HTMLImageElement).parentElement;
                          if (parent) {
                            const fb = parent.querySelector(".rs-avatar") as HTMLElement;
                            if (fb) fb.style.display = "flex";
                          }
                        }}
                      />
                    ) : null}
                    <span
                      className="rs-avatar"
                      style={{
                        backgroundColor: getAvatarColor(station.name),
                        display: station.favicon ? "none" : "flex",
                      }}
                    >
                      {getStationInitials(station.name)}
                    </span>
                  </div>
                  <div className="rs-info">
                    <div className="rs-name">{station.name}</div>
                    <div className="rs-country">{station.country}</div>
                  </div>
                  <span className="rs-chevron" aria-hidden="true">
                    {Icon.ChevronRight(20)}
                  </span>
                </button>
              ))}
              {hasMore && results.length < MAX_RESULTS && (
                <button
                  className="btn btn-secondary rs-more"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  aria-busy={loadingMore}
                >
                  {loadingMore && <span className="spinner-small" aria-hidden="true" />}
                  {loadingMore ? t("presets.loadingMore") : t("presets.loadMore")}
                </button>
              )}
              {results.length >= MAX_RESULTS && (
                <div className="rs-note rs-note--max" title={t("presets.maxReachedTooltip")}>
                  {Icon.Info(18)}
                  <span>{t("presets.maxReached", { count: MAX_RESULTS })}</span>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

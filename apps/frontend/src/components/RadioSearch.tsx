import { useRef, useState } from "react";
import { getErrorMessage, parseApiError } from "../api/types";
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
  onStationSelect: (station: RadioStation) => void;
  isOpen: boolean;
  onClose?: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:7777";

function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const cypress = (window as { Cypress?: { env?: (key: string) => unknown } }).Cypress;
    const apiUrl = cypress?.env?.("apiUrl");
    if (typeof apiUrl === "string" && apiUrl.length > 0) {
      return apiUrl.replace(/\/api\/?$/, "");
    }
  }

  return API_BASE_URL;
}

export default function RadioSearch({ onStationSelect, isOpen, onClose }: RadioSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RadioStation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
          `${baseUrl}/api/radio/search?q=${encodeURIComponent(searchQuery)}&search_type=name&limit=10`,
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
            setError(`HTTP ${response.status}: ${response.statusText}`);
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
    }, 300);
  };

  const handleSelect = (station: RadioStation) => {
    onStationSelect(station);
    setQuery("");
    setResults([]);
    onClose?.();
  };

  if (!isOpen) return null;

  return (
    <div className="radio-search-overlay" onClick={onClose}>
      <div className="radio-search-modal" onClick={(e) => e.stopPropagation()}>
        <div className="search-header">
          <input
            type="search"
            className="search-input"
            placeholder="Sender suchen..."
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            autoFocus
          />
          <button className="search-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="search-results">
          {error && <div className="search-error">{error}</div>}
          {loading && <div className="search-loading">Suche...</div>}
          {!loading && !error && results.length === 0 && query && (
            <div className="search-empty">Keine Sender gefunden</div>
          )}
          {results.map((station) => (
            <button
              key={station.stationuuid}
              className="search-result-item"
              onClick={() => handleSelect(station)}
            >
              <div className="result-name">{station.name}</div>
              <div className="result-country">{station.country}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

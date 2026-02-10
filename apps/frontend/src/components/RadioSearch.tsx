import { useState } from "react";
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

interface RadioSearchProps {
  onStationSelect: (station: RadioStation) => void;
  isOpen: boolean;
  onClose?: () => void;
}

export default function RadioSearch({ onStationSelect, isOpen, onClose }: RadioSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RadioStation[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery);
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setLoading(true);
    // Simulate API search
    setTimeout(() => {
      const mockResults: RadioStation[] = [
        { stationuuid: "1", name: "Absolut relax", country: "Germany" },
        { stationuuid: "2", name: "Bayern 1", country: "Germany" },
        { stationuuid: "3", name: "1LIVE", country: "Germany" },
      ].filter((s) => s.name.toLowerCase().includes(searchQuery.toLowerCase()));
      setResults(mockResults);
      setLoading(false);
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
          {loading && <div className="search-loading">Suche...</div>}
          {!loading && results.length === 0 && query && (
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

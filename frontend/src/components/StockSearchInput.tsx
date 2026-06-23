import { useEffect, useRef, useState } from "react";
import { api, Market, StockSearchResult } from "../api";

const INDIAN_EXCHANGES = /^(NSI|BSE|NSE|BOM|NSEI)$/i;

function filterResults(results: StockSearchResult[], market: Market): StockSearchResult[] {
  if (market === "IN") {
    return results.filter(
      (r) =>
        r.symbol.endsWith(".NS") ||
        r.symbol.endsWith(".BO") ||
        INDIAN_EXCHANGES.test(r.exchange)
    );
  }
  return results.filter(
    (r) =>
      !r.symbol.endsWith(".NS") &&
      !r.symbol.endsWith(".BO") &&
      !INDIAN_EXCHANGES.test(r.exchange)
  );
}

interface Props {
  market: Market;
  onAdd: (symbol: string, market: Market, name?: string) => Promise<void>;
  error?: string;
}

export default function StockSearchInput({ market, onAdd, error }: Props) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const placeholder =
    market === "IN"
      ? "Type name or symbol, e.g. Reliance"
      : "Type name or symbol, e.g. Microsoft";

  const hint =
    market === "IN"
      ? "Indian stocks use .NS suffix (e.g. RELIANCE.NS, TCS.NS)"
      : "US stocks like AAPL, MSFT, TSLA";

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api.searchStocks(query);
        const filtered = filterResults(data.results, market);
        setSuggestions(filtered);
        setOpen(filtered.length > 0);
        setActiveIndex(-1);
      } catch {
        setSuggestions([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, market]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const pick = async (item: StockSearchResult) => {
    setQuery("");
    setOpen(false);
    setSuggestions([]);
    await onAdd(item.symbol, market, item.name);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    if (activeIndex >= 0 && suggestions[activeIndex]) {
      await pick(suggestions[activeIndex]);
      return;
    }

    const symbol = trimmed.toUpperCase();
    setQuery("");
    setOpen(false);
    await onAdd(symbol, market);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="search-wrapper" ref={wrapperRef}>
      <form className="add-form" onSubmit={handleSubmit}>
        <input
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary" disabled={!query.trim()}>
          Add
        </button>
      </form>

      {open && (
        <ul className="search-suggestions">
          {loading && suggestions.length === 0 && (
            <li className="search-item muted">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={`${item.symbol}-${i}`}
              className={`search-item ${i === activeIndex ? "active" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(item);
              }}
            >
              <div className="search-item-main">
                <span className="search-symbol">{item.symbol}</span>
                <span className="search-name">{item.name}</span>
              </div>
              <span className="search-exchange">{item.exchange}</span>
            </li>
          ))}
        </ul>
      )}

      {error && <div className="error">{error}</div>}
      <p className="search-hint">{hint}</p>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { api, HoldingFormData, Market, StockSearchResult } from "../api";
import { currencyForMarket } from "../api";

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
  onAdd: (data: HoldingFormData) => Promise<void>;
  error?: string;
}

export default function HoldingsAdd({ market, onAdd, error }: Props) {
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<StockSearchResult | null>(null);
  const [avgCost, setAvgCost] = useState("");
  const [shares, setShares] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [localError, setLocalError] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const displayError = localError || error;
  const currency = currencyForMarket(market);

  useEffect(() => {
    setLocalError("");
    if (picked || query.trim().length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await api.searchStocks(query.trim());
        const filtered = filterResults(data.results, market);
        setSuggestions(filtered);
        setOpen(filtered.length > 0);
        setActiveIndex(-1);
      } catch {
        setSuggestions([]);
        setOpen(false);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, market, picked]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const resetForm = () => {
    setQuery("");
    setPicked(null);
    setAvgCost("");
    setShares("");
    setPurchaseDate("");
    setSuggestions([]);
    setOpen(false);
  };

  const selectSymbol = (item: StockSearchResult) => {
    setPicked(item);
    setQuery(item.symbol);
    setOpen(false);
    setSuggestions([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError("");

    const symbol = picked?.symbol || query.trim().toUpperCase();
    if (!symbol) {
      setLocalError("Pick a stock from search suggestions");
      return;
    }

    const avg = parseFloat(avgCost);
    if (!Number.isFinite(avg) || avg <= 0) {
      setLocalError("Enter a valid average purchase price");
      return;
    }

    const shareNum = shares.trim() ? parseFloat(shares) : undefined;
    if (shares.trim() && (!Number.isFinite(shareNum!) || shareNum! <= 0)) {
      setLocalError("Shares must be a positive number");
      return;
    }

    setLoading(true);
    try {
      await onAdd({
        symbol,
        name: picked?.name,
        avg_cost: avg,
        shares: shareNum,
        purchase_date: purchaseDate || undefined,
      });
      resetForm();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Failed to add holding");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (picked || !open || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectSymbol(suggestions[activeIndex]);
    }
  };

  return (
    <div className="search-wrapper holdings-add" ref={wrapperRef}>
      <form className="holdings-add-form" onSubmit={handleSubmit}>
        <label className="holdings-field-label" htmlFor="holding-symbol">
          Stock
        </label>
        <input
          id="holding-symbol"
          className="holdings-input"
          type="text"
          placeholder={market === "IN" ? "Search e.g. RELIANCE.NS" : "Search e.g. AAPL"}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPicked(null);
            setLocalError("");
          }}
          onFocus={() => !picked && suggestions.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          autoComplete="off"
          disabled={loading}
        />

        {open && !picked && (
          <ul className="search-suggestions">
            {searching && suggestions.length === 0 && (
              <li className="search-item muted">Searching…</li>
            )}
            {suggestions.map((item, i) => (
              <li
                key={`${item.symbol}-${i}`}
                className={`search-item ${i === activeIndex ? "active" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectSymbol(item);
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

        {picked && (
          <p className="holdings-picked-name">{picked.name}</p>
        )}

        <div className="holdings-fields-row">
          <div className="holdings-field">
            <label className="holdings-field-label" htmlFor="holding-avg">
              Avg purchase price ({currency}) *
            </label>
            <input
              id="holding-avg"
              className="holdings-input"
              type="number"
              step="any"
              min="0"
              placeholder="e.g. 150.25"
              value={avgCost}
              onChange={(e) => setAvgCost(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div className="holdings-field">
            <label className="holdings-field-label" htmlFor="holding-shares">
              Shares (optional)
            </label>
            <input
              id="holding-shares"
              className="holdings-input"
              type="number"
              step="any"
              min="0"
              placeholder="e.g. 10"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <div className="holdings-field">
          <label className="holdings-field-label" htmlFor="holding-date">
            Purchase date (optional)
          </label>
          <input
            id="holding-date"
            className="holdings-input"
            type="date"
            value={purchaseDate}
            onChange={(e) => setPurchaseDate(e.target.value)}
            disabled={loading}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary holdings-add-btn"
          disabled={loading || !query.trim() || !avgCost.trim()}
        >
          {loading ? "Adding…" : "Add holding & analyze"}
        </button>
      </form>

      {displayError && <div className="error">{displayError}</div>}

      <p className="search-hint">
        Search by company name or ticker — same as the wishlist. Average cost is required so we can show your P&amp;L.
      </p>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { api, BulkAddResult, Market, StockSearchResult } from "../api";
import { parseSymbolList } from "../utils/symbols";

const INDIAN_EXCHANGES = /^(NSI|BSE|NSE|BOM|NSEI)$/i;
const MULTI_SYMBOL = /[,;\n]/;

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

function formatBulkSummary(res: BulkAddResult): string {
  const parts: string[] = [];
  if (res.added.length > 0) {
    parts.push(`Added ${res.added.length} symbol${res.added.length === 1 ? "" : "s"}`);
  }
  if (res.skipped.length > 0) {
    parts.push(`skipped ${res.skipped.length} already in list`);
  }
  if (res.invalid.length > 0) {
    parts.push(`${res.invalid.length} invalid`);
  }
  return parts.join(" · ");
}

interface Props {
  market: Market;
  onAdd: (symbol: string, market: Market, name?: string) => Promise<void>;
  onBulkComplete: (result: BulkAddResult) => Promise<void>;
  error?: string;
}

export default function WishlistAdd({ market, onAdd, onBulkComplete, error }: Props) {
  const [text, setText] = useState("");
  const [localError, setLocalError] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [summary, setSummary] = useState("");
  const wrapperRef = useRef<HTMLDivElement>(null);

  const symbols = parseSymbolList(text);
  const isBulk = MULTI_SYMBOL.test(text);
  const displayError = localError || error;

  const placeholder =
    market === "IN"
      ? "One symbol or paste a list:\nRELIANCE.NS, HDFCBANK.NS, TCS.NS"
      : "One symbol or paste a list:\nAAPL, MSFT, NVDA";

  useEffect(() => {
    setLocalError("");
    setSummary("");
    if (isBulk || text.trim().length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await api.searchStocks(text.trim());
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
  }, [text, market, isBulk]);

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
    setText("");
    setOpen(false);
    setSuggestions([]);
    setLoading(true);
    setLocalError("");
    try {
      await onAdd(item.symbol, market, item.name);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;

    if (!isBulk && activeIndex >= 0 && suggestions[activeIndex]) {
      await pick(suggestions[activeIndex]);
      return;
    }

    setLoading(true);
    setLocalError("");
    setSummary("");
    setOpen(false);

    try {
      if (symbols.length > 1) {
        const res = await api.bulkAddToWishlist(symbols, market);
        setText("");
        setSummary(formatBulkSummary(res));
        await onBulkComplete(res);
      } else if (symbols.length === 1) {
        const symbol = symbols[0];
        setText("");
        await onAdd(symbol, market);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0 || isBulk) return;

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

  const submitLabel =
    symbols.length > 1
      ? loading
        ? "Importing…"
        : `Import ${symbols.length}`
      : loading
        ? "Adding…"
        : "Add";

  return (
    <div className="search-wrapper wishlist-add" ref={wrapperRef}>
      <form className="wishlist-add-form" onSubmit={handleSubmit}>
        <textarea
          className="wishlist-add-input"
          placeholder={placeholder}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setSummary("");
            setLocalError("");
          }}
          onFocus={() => !isBulk && suggestions.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
          rows={3}
          spellCheck={false}
          autoComplete="off"
        />
        <button
          type="submit"
          className="btn btn-primary wishlist-add-btn"
          disabled={loading || !text.trim()}
        >
          {submitLabel}
        </button>
      </form>

      {open && !isBulk && (
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

      {displayError && <div className="error">{displayError}</div>}
      {summary && <div className="bulk-upload-result">{summary}</div>}

      <p className="search-hint">
        {symbols.length > 1
          ? `${symbols.length} symbols ready — duplicates are skipped automatically`
          : market === "IN"
            ? "Indian stocks use .NS suffix. Paste comma-separated lists to add many at once."
            : "Paste comma-separated symbols to add many at once (e.g. AAPL, MSFT, TSLA)."}
      </p>
    </div>
  );
}

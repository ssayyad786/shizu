import { useState } from "react";
import { api, BulkAddResult, Market } from "../api";
import { parseSymbolList } from "../utils/symbols";

interface Props {
  market: Market;
  onComplete: (result: BulkAddResult) => Promise<void>;
}

export default function BulkWishlistUpload({ market, onComplete }: Props) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BulkAddResult | null>(null);
  const [error, setError] = useState("");

  const symbolCount = parseSymbolList(text).length;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const symbols = parseSymbolList(text);
    if (symbols.length === 0) return;

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.bulkAddToWishlist(symbols, market);
      setResult(res);
      setText("");
      await onComplete(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk import failed");
    } finally {
      setLoading(false);
    }
  };

  const placeholder =
    market === "IN"
      ? "RELIANCE.NS, HDFCBANK.NS, TCS.NS\n(one per line or comma-separated)"
      : "AAPL, MSFT, NVDA\n(one per line or comma-separated)";

  return (
    <div className="bulk-upload">
      <button
        type="button"
        className="bulk-upload-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? "▾" : "▸"} Bulk add symbols
      </button>

      {open && (
        <form className="bulk-upload-form" onSubmit={handleSubmit}>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setResult(null);
              setError("");
            }}
            placeholder={placeholder}
            rows={5}
            spellCheck={false}
          />
          <div className="bulk-upload-actions">
            <span className="bulk-upload-count">
              {symbolCount > 0 ? `${symbolCount} symbol${symbolCount === 1 ? "" : "s"}` : "Paste symbols above"}
            </span>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || symbolCount === 0}
            >
              {loading ? "Importing…" : "Import list"}
            </button>
          </div>
          {error && <div className="error">{error}</div>}
          {result && (
            <div className="bulk-upload-result">
              <strong>
                Added {result.added.length}
                {result.skipped.length > 0 && ` · Skipped ${result.skipped.length} duplicate${result.skipped.length === 1 ? "" : "s"}`}
                {result.invalid.length > 0 && ` · ${result.invalid.length} invalid`}
              </strong>
              {result.invalid.length > 0 && (
                <p className="bulk-upload-invalid">
                  {result.invalid.slice(0, 5).map((i) => `${i.symbol}: ${i.reason}`).join(" · ")}
                  {result.invalid.length > 5 && ` · +${result.invalid.length - 5} more`}
                </p>
              )}
            </div>
          )}
        </form>
      )}
    </div>
  );
}

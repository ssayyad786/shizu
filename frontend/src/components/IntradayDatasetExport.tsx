import { useEffect, useMemo, useState } from "react";
import { api, IntradayReportFormat, IntradayTradeDate } from "../api";

type Props = {
  onError?: (message: string) => void;
};

export default function IntradayDatasetExport({ onError }: Props) {
  const [dates, setDates] = useState<IntradayTradeDate[]>([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [trainRatio, setTrainRatio] = useState(80);
  const [includeSplit, setIncludeSplit] = useState(true);
  const [loadingDates, setLoadingDates] = useState(true);
  const [downloading, setDownloading] = useState<IntradayReportFormat | null>(null);

  useEffect(() => {
    api
      .getIntradayTradeDates()
      .then((res) => {
        setDates(res.dates);
        if (res.dates.length > 0) {
          const latest = res.dates[0].date;
          setFromDate(latest);
          setToDate(latest);
        }
      })
      .catch(() => onError?.("Failed to load trade dates"))
      .finally(() => setLoadingDates(false));
  }, [onError]);

  const selectedCount = useMemo(() => {
    if (!fromDate && !toDate) return null;
    const from = fromDate || toDate;
    const to = toDate || fromDate;
    return dates
      .filter((d) => d.date >= from && d.date <= to)
      .reduce((sum, d) => sum + d.trades, 0);
  }, [dates, fromDate, toDate]);

  const handleDownload = async (format: IntradayReportFormat) => {
    setDownloading(format);
    try {
      await api.downloadIntradayDataset({
        format,
        fromDate: fromDate || undefined,
        toDate: toDate || undefined,
        trainRatio: trainRatio / 100,
        split: includeSplit,
      });
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Failed to download dataset");
    } finally {
      setDownloading(null);
    }
  };

  const pickDate = (date: string) => {
    setFromDate(date);
    setToDate(date);
  };

  return (
    <div className="intraday-dataset-bar">
      <div className="intraday-dataset-header">
        <div>
          <strong>Train / test dataset</strong>
          <span>
            Select dates, export features + labels from past trades for model tuning or ML experiments.
          </span>
        </div>
      </div>

      <div className="intraday-dataset-fields">
        <label className="intraday-date-field">
          <span>From</span>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            disabled={loadingDates}
          />
        </label>
        <label className="intraday-date-field">
          <span>To</span>
          <input
            type="date"
            value={toDate}
            min={fromDate || undefined}
            onChange={(e) => setToDate(e.target.value)}
            disabled={loadingDates}
          />
        </label>
        <label className="intraday-date-field intraday-split-field">
          <span>Train %</span>
          <input
            type="number"
            min={50}
            max={95}
            value={trainRatio}
            onChange={(e) => setTrainRatio(Number(e.target.value))}
            disabled={!includeSplit}
          />
        </label>
        <label className="intraday-checkbox-field">
          <input
            type="checkbox"
            checked={includeSplit}
            onChange={(e) => setIncludeSplit(e.target.checked)}
          />
          <span>Train / test split</span>
        </label>
      </div>

      {dates.length > 0 && (
        <div className="intraday-date-chips">
          <span className="intraday-date-chips-label">Quick pick:</span>
          {dates.slice(0, 8).map((d) => (
            <button
              key={d.date}
              type="button"
              className={`intraday-date-chip ${fromDate === d.date && toDate === d.date ? "active" : ""}`}
              onClick={() => pickDate(d.date)}
            >
              {d.date} ({d.closed} closed)
            </button>
          ))}
        </div>
      )}

      {loadingDates ? (
        <p className="intraday-dataset-meta">Loading available dates…</p>
      ) : dates.length === 0 ? (
        <p className="intraday-dataset-meta">No trade history yet — run scans during market hours first.</p>
      ) : (
        <p className="intraday-dataset-meta">
          {selectedCount != null ? `${selectedCount} trade(s) in range` : "All dates"} ·
          {" "}JSON includes <code>train</code> / <code>test</code> arrays with factor features and win labels
        </p>
      )}

      <div className="intraday-report-download">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleDownload("json")}
          disabled={downloading !== null || dates.length === 0}
        >
          {downloading === "json" ? "Downloading…" : "Export train/test JSON"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleDownload("csv")}
          disabled={downloading !== null || dates.length === 0}
        >
          {downloading === "csv" ? "Downloading…" : "Export CSV"}
        </button>
      </div>
    </div>
  );
}

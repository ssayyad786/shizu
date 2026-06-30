import { useState } from "react";
import { api, IntradayReportFormat } from "../api";

type Props = {
  compact?: boolean;
  onError?: (message: string) => void;
};

export default function IntradayReportDownload({ compact, onError }: Props) {
  const [downloading, setDownloading] = useState<IntradayReportFormat | null>(null);

  const handleDownload = async (format: IntradayReportFormat) => {
    setDownloading(format);
    try {
      await api.downloadIntradayReport(format);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Failed to download report");
    } finally {
      setDownloading(null);
    }
  };

  if (compact) {
    return (
      <div className="intraday-report-download compact">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleDownload("json")}
          disabled={downloading !== null}
          title="Full report with factor analysis and tuning insights"
        >
          {downloading === "json" ? "Downloading…" : "↓ JSON report"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleDownload("csv")}
          disabled={downloading !== null}
          title="Trade log for spreadsheets"
        >
          {downloading === "csv" ? "Downloading…" : "↓ CSV log"}
        </button>
      </div>
    );
  }

  return (
    <div className="intraday-report-bar">
      <div className="intraday-report-bar-text">
        <strong>Algo review report</strong>
        <span>Export trades, factor scores, and tuning insights to improve the model.</span>
      </div>
      <div className="intraday-report-download">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleDownload("json")}
          disabled={downloading !== null}
        >
          {downloading === "json" ? "Downloading…" : "Download JSON"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleDownload("csv")}
          disabled={downloading !== null}
        >
          {downloading === "csv" ? "Downloading…" : "Download CSV"}
        </button>
      </div>
    </div>
  );
}

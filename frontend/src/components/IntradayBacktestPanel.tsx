import { useState } from "react";
import { api, IntradayBacktestResult } from "../api";

type Props = {
  watchlistSymbols: string[];
  onError?: (message: string) => void;
};

function statusLabel(status: string) {
  switch (status) {
    case "target_hit":
      return "Target 1 hit";
    case "target_2_hit":
      return "Target 2 hit";
    case "stop_hit":
      return "Stop hit";
    case "expired_win":
      return "Session end — profit";
    case "expired_loss":
      return "Session end — loss";
    default:
      return status;
  }
}

export default function IntradayBacktestPanel({ watchlistSymbols, onError }: Props) {
  const [symbol, setSymbol] = useState(watchlistSymbols[0] ?? "AAPL");
  const [date, setDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IntradayBacktestResult | null>(null);

  const runReplay = async () => {
    if (!symbol.trim() || !date) {
      onError?.("Pick a symbol and date");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.runIntradayBacktest(symbol.trim().toUpperCase(), date);
      setResult(res);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="intraday-backtest-bar">
      <div className="intraday-dataset-header">
        <div>
          <strong>Replay backtest</strong>
          <span>
            Pick any US symbol and date — reruns <em>current</em> intraday rules on Yahoo 5m/15m history
            and simulates hit or fail.
          </span>
        </div>
      </div>

      <div className="intraday-dataset-fields">
        <label className="intraday-date-field">
          <span>Symbol</span>
          <input
            type="text"
            list="intraday-backtest-symbols"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="AAPL"
          />
          <datalist id="intraday-backtest-symbols">
            {watchlistSymbols.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </label>
        <label className="intraday-date-field">
          <span>Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <button
          type="button"
          className="btn btn-primary intraday-replay-btn"
          onClick={runReplay}
          disabled={loading || !date}
        >
          {loading ? "Replaying…" : "Run replay"}
        </button>
      </div>

      {result && (
        <div className="intraday-backtest-result">
          {!result.traded ? (
            <p className="intraday-backtest-no-trade">{result.message}</p>
          ) : (
            <>
              <div className="intraday-backtest-outcome">
                <span className={`intraday-backtest-badge ${result.outcome?.success ? "win" : "loss"}`}>
                  {statusLabel(result.outcome?.status ?? "")}
                </span>
                <strong>
                  {result.outcome && result.outcome.result_pct > 0 ? "+" : ""}
                  {result.outcome?.result_pct}%
                </strong>
                <span className="intraday-backtest-meta">
                  Entry {result.entry_time_et?.slice(11, 16)} ET · {result.scans_run} scans
                </span>
              </div>
              {result.trade_plan && (
                <div className="intraday-levels compact">
                  <div><span>{result.trade_plan.direction}</span><strong>${result.trade_plan.entry_price}</strong></div>
                  <div className="target-text"><span>T1</span><strong>${result.trade_plan.target_1}</strong></div>
                  <div className="target-text"><span>T2</span><strong>${result.trade_plan.target_2}</strong></div>
                  <div className="stop-text"><span>Stop</span><strong>${result.trade_plan.stop_loss}</strong></div>
                  <div><span>Score</span><strong>{result.signal?.score}</strong></div>
                  <div><span>Conf</span><strong>{result.signal?.confidence}%</strong></div>
                </div>
              )}
              {result.signal?.summary && <p className="intraday-summary">{result.signal.summary}</p>}
              {result.outcome && (
                <p className="intraday-dataset-meta">
                  MFE {result.outcome.mfe_pct > 0 ? "+" : ""}{result.outcome.mfe_pct}% ·
                  MAE {result.outcome.mae_pct}% · R:R {result.trade_plan?.risk_reward}:1
                </p>
              )}
            </>
          )}

          {result.recorded_trade && (
            <div className="intraday-backtest-recorded">
              <strong>Actually recorded that day:</strong>{" "}
              {result.recorded_trade.direction} @ ${result.recorded_trade.entry_price} →{" "}
              {statusLabel(result.recorded_trade.status)} ({result.recorded_trade.result_pct}%)
            </div>
          )}
        </div>
      )}
    </div>
  );
}

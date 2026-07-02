import { useState } from "react";
import { api, IntradayBacktestRangeResult, IntradayBacktestResult } from "../api";

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

function isRangeResult(
  res: IntradayBacktestResult | IntradayBacktestRangeResult
): res is IntradayBacktestRangeResult {
  return res.replay_type === "shizu_intraday_backtest_range";
}

function SingleDayResult({ result }: { result: IntradayBacktestResult }) {
  return (
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
              <div>
                <span>{result.trade_plan.direction}</span>
                <strong>${result.trade_plan.entry_price}</strong>
              </div>
              <div className="target-text">
                <span>T1</span>
                <strong>${result.trade_plan.target_1}</strong>
              </div>
              <div className="target-text">
                <span>T2</span>
                <strong>${result.trade_plan.target_2}</strong>
              </div>
              <div className="stop-text">
                <span>Stop</span>
                <strong>${result.trade_plan.stop_loss}</strong>
              </div>
              <div>
                <span>Score</span>
                <strong>{result.signal?.score}</strong>
              </div>
              <div>
                <span>Conf</span>
                <strong>{result.signal?.confidence}%</strong>
              </div>
            </div>
          )}
          {result.signal?.summary && <p className="intraday-summary">{result.signal.summary}</p>}
          {result.outcome && (
            <p className="intraday-dataset-meta">
              MFE {result.outcome.mfe_pct > 0 ? "+" : ""}
              {result.outcome.mfe_pct}% · MAE {result.outcome.mae_pct}% · R:R{" "}
              {result.trade_plan?.risk_reward}:1
            </p>
          )}
        </>
      )}

      {result.recorded_trade && (
        <div className="intraday-backtest-recorded">
          <strong>Actually recorded that day:</strong> {result.recorded_trade.direction} @ $
          {result.recorded_trade.entry_price} → {statusLabel(result.recorded_trade.status)} (
          {result.recorded_trade.result_pct}%)
        </div>
      )}
    </div>
  );
}

function RangeResult({ result }: { result: IntradayBacktestRangeResult }) {
  const [expandedDate, setExpandedDate] = useState<string | null>(null);
  const expanded = result.results.find((r) => r.date === expandedDate) ?? null;

  return (
    <div className="intraday-backtest-result">
      <div className="intraday-backtest-range-summary">
        <div className="intraday-backtest-range-stat">
          <span>Trading days</span>
          <strong>{result.trading_days}</strong>
        </div>
        <div className="intraday-backtest-range-stat">
          <span>Trades</span>
          <strong>{result.trades}</strong>
        </div>
        <div className="intraday-backtest-range-stat">
          <span>Wins / losses</span>
          <strong>
            {result.wins} / {result.losses}
          </strong>
        </div>
        <div className="intraday-backtest-range-stat">
          <span>Win rate</span>
          <strong>{result.win_rate}%</strong>
        </div>
        <div className="intraday-backtest-range-stat">
          <span>Total P&amp;L</span>
          <strong className={result.total_result_pct >= 0 ? "win-text" : "loss-text"}>
            {result.total_result_pct > 0 ? "+" : ""}
            {result.total_result_pct}%
          </strong>
        </div>
        <div className="intraday-backtest-range-stat">
          <span>Avg / trade</span>
          <strong>
            {result.avg_result_pct > 0 ? "+" : ""}
            {result.avg_result_pct}%
          </strong>
        </div>
      </div>

      <p className="intraday-dataset-meta">
        {result.start_date} → {result.end_date} · {result.no_trade_days} day(s) with no trade
      </p>

      <div className="intraday-backtest-range-table-wrap">
        <table className="intraday-backtest-range-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Result</th>
              <th>P&amp;L</th>
              <th>Entry</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {result.results.map((day) => (
              <tr
                key={day.date}
                className={expandedDate === day.date ? "expanded" : ""}
                onClick={() => setExpandedDate(expandedDate === day.date ? null : day.date)}
              >
                <td>{day.date}</td>
                <td>
                  {!day.traded ? (
                    <span className="intraday-backtest-muted">No trade</span>
                  ) : (
                    <span className={`intraday-backtest-badge ${day.outcome?.success ? "win" : "loss"}`}>
                      {statusLabel(day.outcome?.status ?? "")}
                    </span>
                  )}
                </td>
                <td>
                  {day.traded ? (
                    <strong className={day.outcome?.success ? "win-text" : "loss-text"}>
                      {day.outcome && day.outcome.result_pct > 0 ? "+" : ""}
                      {day.outcome?.result_pct}%
                    </strong>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{day.entry_time_et ? day.entry_time_et.slice(11, 16) + " ET" : "—"}</td>
                <td>{day.trade_plan?.direction ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {expanded && (
        <div className="intraday-backtest-range-detail">
          <strong>{expanded.date}</strong>
          <SingleDayResult result={expanded} />
        </div>
      )}
    </div>
  );
}

export default function IntradayBacktestPanel({ watchlistSymbols, onError }: Props) {
  const [symbol, setSymbol] = useState(watchlistSymbols[0] ?? "AAPL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IntradayBacktestResult | IntradayBacktestRangeResult | null>(null);

  const runReplay = async () => {
    if (!symbol.trim() || !startDate) {
      onError?.("Pick a symbol and start date");
      return;
    }
    if (endDate && endDate < startDate) {
      onError?.("End date must be on or after start date");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.runIntradayBacktest(
        symbol.trim().toUpperCase(),
        startDate,
        endDate || undefined
      );
      setResult(res);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const isRange = Boolean(endDate && endDate !== startDate);

  return (
    <div className="intraday-backtest-bar">
      <div className="intraday-dataset-header">
        <div>
          <strong>Replay backtest</strong>
          <span>
            Pick any US symbol and date (or range) — reruns <em>current</em> intraday rules on Yahoo 5m/15m
            history and simulates hit or fail for each trading day.
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
          <span>{isRange ? "From" : "Date"}</span>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </label>
        <label className="intraday-date-field">
          <span>To (optional)</span>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={startDate || undefined} />
        </label>
        <button
          type="button"
          className="btn btn-primary intraday-replay-btn"
          onClick={runReplay}
          disabled={loading || !startDate}
        >
          {loading ? "Replaying…" : isRange ? "Run range replay" : "Run replay"}
        </button>
      </div>

      {result &&
        (isRangeResult(result) ? <RangeResult result={result} /> : <SingleDayResult result={result} />)}
    </div>
  );
}

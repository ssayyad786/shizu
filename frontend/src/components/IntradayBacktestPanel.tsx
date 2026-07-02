import { useCallback, useRef, useState } from "react";
import {
  api,
  INTRADAY_MAX_RANGE_CALENDAR_DAYS,
  INTRADAY_MAX_RANGE_TRADING_DAYS,
  IntradayBacktestRangeResult,
  IntradayBacktestResult,
} from "../api";

type Props = {
  watchlistSymbols: string[];
  onError?: (message: string) => void;
};

type RangeProgress = {
  total: number;
  done: number;
  current: string | null;
  etaSec: number | null;
  cancelled?: boolean;
};

const TABLE_PAGE_SIZE = 20;

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
  return "replay_type" in res && res.replay_type === "shizu_intraday_backtest_range";
}

function formatEta(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  if (seconds < 5) return "almost done";
  if (seconds < 60) return `~${Math.ceil(seconds)}s left`;
  const mins = Math.ceil(seconds / 60);
  return mins === 1 ? "~1 min left" : `~${mins} min left`;
}

function calendarSpanDays(start: string, end: string): number {
  const a = new Date(`${start}T12:00:00`).getTime();
  const b = new Date(`${end}T12:00:00`).getTime();
  return Math.round(Math.abs(b - a) / 86_400_000);
}

function buildRangeResult(
  symbol: string,
  startDate: string,
  endDate: string,
  results: IntradayBacktestResult[],
  cancelled = false
): IntradayBacktestRangeResult {
  const traded = results.filter((r) => r.traded);
  const wins = traded.filter((r) => r.outcome?.success);
  const losses = traded.filter((r) => !r.outcome?.success);
  const noTrade = results.filter((r) => !r.traded);
  const totalPct = traded.reduce((sum, r) => sum + (r.outcome?.result_pct ?? 0), 0);

  return {
    replay_type: "shizu_intraday_backtest_range",
    symbol,
    start_date: startDate,
    end_date: endDate,
    trading_days: results.length,
    trades: traded.length,
    wins: wins.length,
    losses: losses.length,
    no_trade_days: noTrade.length,
    win_rate: traded.length ? Math.round((wins.length / traded.length) * 1000) / 10 : 0,
    total_result_pct: Math.round(totalPct * 100) / 100,
    avg_result_pct: traded.length ? Math.round((totalPct / traded.length) * 100) / 100 : 0,
    results,
    notes: cancelled
      ? [`Stopped early — ${results.length} day(s) replayed.`]
      : undefined,
  };
}

function RangeProgressBar({
  progress,
  onStop,
}: {
  progress: RangeProgress;
  onStop?: () => void;
}) {
  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  const eta = formatEta(progress.etaSec);
  const running = progress.done < progress.total && !progress.cancelled;

  return (
    <div className="intraday-backtest-progress">
      <div className="intraday-backtest-progress-header">
        <span>
          {progress.cancelled ? "Stopped — " : ""}
          {progress.done} of {progress.total} trading day{progress.total === 1 ? "" : "s"} done
          {running && progress.current ? ` · replaying ${progress.current}` : ""}
          {!running && !progress.cancelled && progress.done === progress.total ? " · complete" : ""}
        </span>
        <span className="intraday-backtest-progress-actions">
          {eta && running && <span className="intraday-backtest-progress-eta">{eta}</span>}
          {running && onStop && (
            <button type="button" className="btn btn-ghost btn-sm intraday-stop-btn" onClick={onStop}>
              Stop
            </button>
          )}
        </span>
      </div>
      <div className="intraday-backtest-progress-track" aria-hidden>
        <div
          className={`intraday-backtest-progress-fill${progress.cancelled ? " cancelled" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
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

function RangeResult({
  result,
  progress,
  onStop,
}: {
  result: IntradayBacktestRangeResult;
  progress?: RangeProgress | null;
  onStop?: () => void;
}) {
  const [expandedDate, setExpandedDate] = useState<string | null>(null);
  const [tableLimit, setTableLimit] = useState(TABLE_PAGE_SIZE);
  const expanded = result.results.find((r) => r.date === expandedDate) ?? null;
  const running = progress != null && progress.done < progress.total && !progress.cancelled;
  const loading = running;
  const visibleRows = result.results.slice(0, tableLimit);
  const hasMoreRows = result.results.length > tableLimit;

  return (
    <div className="intraday-backtest-result">
      {progress && progress.total > 1 && <RangeProgressBar progress={progress} onStop={onStop} />}

      {!loading && (
        <>
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
            {result.notes?.[0] ? ` · ${result.notes[0]}` : ""}
          </p>
        </>
      )}

      {result.results.length > 0 && (
        <div className="intraday-backtest-range-table-wrap">
          <table className="intraday-backtest-range-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Result</th>
                <th>P&amp;L</th>
                <th>Entry</th>
                <th>Direction</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((day) => (
                <tr
                  key={day.date}
                  className={expandedDate === day.date ? "expanded" : ""}
                  onClick={() => !loading && setExpandedDate(expandedDate === day.date ? null : day.date)}
                >
                  <td>{day.date}</td>
                  <td>
                    <span className="intraday-backtest-day-done">Done</span>
                  </td>
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
              {loading && progress?.current && (
                <tr className="intraday-backtest-row-active">
                  <td>{progress.current}</td>
                  <td>
                    <span className="intraday-backtest-day-running">Running…</span>
                  </td>
                  <td colSpan={4} className="intraday-backtest-muted">
                    Replaying intraday bars
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {hasMoreRows && !loading && (
            <button
              type="button"
              className="btn btn-ghost intraday-backtest-show-more"
              onClick={() => setTableLimit((n) => n + TABLE_PAGE_SIZE)}
            >
              Show more ({result.results.length - tableLimit} remaining)
            </button>
          )}
        </div>
      )}

      {expanded && !loading && (
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
  const [rangeProgress, setRangeProgress] = useState<RangeProgress | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const isRange = Boolean(endDate && endDate !== startDate);

  const stopReplay = useCallback(() => {
    abortRef.current?.abort();
    setRangeProgress((p) => (p ? { ...p, cancelled: true, current: null, etaSec: null } : p));
  }, []);

  const validateRange = useCallback(() => {
    if (!isRange) return true;
    const span = calendarSpanDays(startDate, endDate);
    if (span > INTRADAY_MAX_RANGE_CALENDAR_DAYS) {
      onError?.(
        `Range is ${span} calendar days — maximum is ${INTRADAY_MAX_RANGE_CALENDAR_DAYS}. Pick a shorter period.`
      );
      return false;
    }
    return true;
  }, [endDate, isRange, onError, startDate]);

  const runRangeReplay = async (sym: string) => {
    const schedule = await api.getIntradayTradingDays(startDate, endDate);
    const maxDays = schedule.max_trading_days ?? INTRADAY_MAX_RANGE_TRADING_DAYS;
    if (schedule.count > maxDays) {
      throw new Error(
        `Range has ${schedule.count} trading days — maximum is ${maxDays}. Use a shorter range.`
      );
    }

    const days = schedule.trading_days;
    const dayResults: IntradayBacktestResult[] = [];
    const startedAt = Date.now();
    const controller = new AbortController();
    abortRef.current = controller;
    let cancelled = false;

    setRangeProgress({ total: days.length, done: 0, current: days[0] ?? null, etaSec: null });
    setResult(buildRangeResult(sym, startDate, endDate, []));

    for (let i = 0; i < days.length; i++) {
      if (controller.signal.aborted) {
        cancelled = true;
        break;
      }

      const day = days[i];
      setRangeProgress({
        total: days.length,
        done: i,
        current: day,
        etaSec: i > 0 ? ((Date.now() - startedAt) / i) * (days.length - i) / 1000 : null,
      });

      try {
        const dayResult = await api.runIntradayBacktestDay(sym, day, controller.signal);
        dayResults.push(dayResult);
      } catch (e) {
        if (controller.signal.aborted) {
          cancelled = true;
          break;
        }
        dayResults.push({
          symbol: sym,
          date: day,
          traded: false,
          scans_run: 0,
          message: e instanceof Error ? e.message : "Replay failed for this day",
        });
      }

      const elapsedSec = (Date.now() - startedAt) / 1000;
      const remaining = i + 1 < days.length ? (elapsedSec / (i + 1)) * (days.length - i - 1) : 0;

      setRangeProgress({
        total: days.length,
        done: i + 1,
        current: cancelled || i + 1 >= days.length ? null : days[i + 1],
        etaSec: cancelled ? null : remaining,
        cancelled,
      });
      setResult(buildRangeResult(sym, startDate, endDate, dayResults, cancelled));
    }

    abortRef.current = null;
    setRangeProgress(null);
  };

  const runReplay = async () => {
    if (!symbol.trim() || !startDate) {
      onError?.("Pick a symbol and start date");
      return;
    }
    if (endDate && endDate < startDate) {
      onError?.("End date must be on or after start date");
      return;
    }
    if (!validateRange()) return;

    setLoading(true);
    setResult(null);
    setRangeProgress(null);
    abortRef.current?.abort();

    const sym = symbol.trim().toUpperCase();

    try {
      if (isRange) {
        await runRangeReplay(sym);
      } else {
        const res = await api.runIntradayBacktest(sym, startDate);
        setResult(res);
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        onError?.(e instanceof Error ? e.message : "Backtest failed");
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  return (
    <div className="intraday-backtest-bar">
      <div className="intraday-dataset-header">
        <div>
          <strong>Replay backtest</strong>
          <span>
            Pick any US symbol and date (or range) — reruns <em>current</em> intraday rules on Yahoo 5m/15m
            history. Range replays up to {INTRADAY_MAX_RANGE_TRADING_DAYS} trading days.
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
            disabled={loading}
          />
          <datalist id="intraday-backtest-symbols">
            {watchlistSymbols.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </label>
        <label className="intraday-date-field">
          <span>{isRange ? "From" : "Date"}</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            disabled={loading}
          />
        </label>
        <label className="intraday-date-field">
          <span>To (optional)</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            min={startDate || undefined}
            disabled={loading}
          />
        </label>
        <div className="intraday-replay-actions">
          <button
            type="button"
            className="btn btn-primary intraday-replay-btn"
            onClick={runReplay}
            disabled={loading || !startDate}
          >
            {loading
              ? isRange && rangeProgress
                ? `Day ${rangeProgress.done} of ${rangeProgress.total}…`
                : "Replaying…"
              : isRange
                ? "Run range replay"
                : "Run replay"}
          </button>
          {loading && isRange && (
            <button type="button" className="btn btn-ghost intraday-stop-btn" onClick={stopReplay}>
              Stop
            </button>
          )}
        </div>
      </div>

      {result &&
        (isRangeResult(result) ? (
          <RangeResult result={result} progress={rangeProgress} onStop={stopReplay} />
        ) : (
          <SingleDayResult result={result} />
        ))}
    </div>
  );
}

import type { SignalOutlook, StockDetail } from "../api";
import StockChart from "./StockChart";

interface Props {
  detail: StockDetail;
  period: string;
  onPeriodChange: (period: string) => void;
}

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y"];

function bannerClass(action: string, canEarn: boolean): string {
  if (canEarn) return "earn";
  if (action.includes("SELL")) return "caution";
  return "neutral";
}

function fmtMoney(value: number, currency: string) {
  const sym = currency === "INR" ? "₹" : "$";
  return `${sym}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function signalTitle(action: string, canEarn: boolean): string {
  if (canEarn) return "Buy signal — short-term trade plan";
  if (action.includes("SELL")) return "Caution signal";
  return "Market signal — why HOLD";
}

function upperLabel(canEarn: boolean, action: string): string {
  if (canEarn) return "Upper target (sell)";
  if (action.includes("SELL")) return "Upper (bounce resistance)";
  return "Upper target (resistance)";
}

function lowerLabel(canEarn: boolean, action: string): string {
  if (canEarn) return "Lower target (stop loss)";
  if (action.includes("SELL")) return "Lower target (downside)";
  return "Lower target (support)";
}

function MarketSignalPanel({
  signal,
  outlook,
  currency,
}: {
  signal: StockDetail["signal"];
  outlook: SignalOutlook;
  currency: string;
}) {
  const canEarn = signal.can_earn;

  return (
    <div className={`signal-banner signal-banner-rich ${bannerClass(signal.action, canEarn)}`}>
      <h3>{signalTitle(signal.action, canEarn)}</h3>
      <p className="signal-summary">{signal.summary}</p>

      <div className="signal-section">
        <h4>Why we say {signal.action.replace("_", " ")}</h4>
        <ul className="signal-reasoning">
          {outlook.reasoning.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </div>

      <div className="signal-section">
        <h4>Expected price range</h4>
        <div className="signal-targets">
          <div className="signal-target target-upper">
            <span className="signal-target-label">{upperLabel(canEarn, signal.action)}</span>
            <span className="signal-target-price">{fmtMoney(outlook.upper_target, currency)}</span>
            <span className="signal-target-pct">
              {outlook.upper_pct >= 0 ? "+" : ""}
              {outlook.upper_pct.toFixed(2)}%
            </span>
          </div>
          {outlook.mid_level != null && (
            <div className="signal-target target-mid">
              <span className="signal-target-label">Mid level</span>
              <span className="signal-target-price">{fmtMoney(outlook.mid_level, currency)}</span>
            </div>
          )}
          <div className="signal-target target-lower">
            <span className="signal-target-label">{lowerLabel(canEarn, signal.action)}</span>
            <span className="signal-target-price">{fmtMoney(outlook.lower_target, currency)}</span>
            <span className="signal-target-pct">
              {outlook.lower_pct >= 0 ? "+" : ""}
              {outlook.lower_pct.toFixed(2)}%
            </span>
          </div>
        </div>
        <p className="signal-range-note">{outlook.range_note}</p>
        {canEarn && signal.trade_plan && (
          <p className="signal-range-note">
            Entry {fmtMoney(signal.trade_plan.entry_price, currency)} · expect target in ~
            {signal.trade_plan.hold_days} trading day{signal.trade_plan.hold_days === 1 ? "" : "s"} (max 10) ·
            tracked in History
          </p>
        )}
      </div>
    </div>
  );
}

export default function StockDetailView({ detail, period, onPeriodChange }: Props) {
  const { quote, signal, candles, indicators } = detail;
  const isUp = quote.change >= 0;

  return (
    <div>
      <div className="detail-header">
        <div className="price-block">
          <div className="symbol">{quote.symbol}</div>
          <div className="price">
            {quote.currency === "INR" ? "₹" : "$"}
            {quote.price.toLocaleString()}
          </div>
          <div className={`change ${isUp ? "up" : "down"}`}>
            {isUp ? "+" : ""}
            {quote.change.toFixed(2)} ({isUp ? "+" : ""}
            {quote.change_pct.toFixed(2)}%)
          </div>
        </div>
        <div>
          <span className={`action-pill ${signal.action}`}>{signal.action.replace("_", " ")}</span>
          <div className="scan-info" style={{ marginTop: 8 }}>
            Confidence: {signal.confidence}%
          </div>
        </div>
      </div>

      {signal.outlook ? (
        <MarketSignalPanel signal={signal} outlook={signal.outlook} currency={quote.currency} />
      ) : (
        <div className={`signal-banner ${bannerClass(signal.action, signal.can_earn)}`}>
          <h3>{signal.can_earn ? "Buy signal" : "Market signal"}</h3>
          <p>{signal.summary}</p>
        </div>
      )}

      <div className="period-tabs">
        {PERIODS.map((p) => (
          <button key={p} className={period === p ? "active" : ""} onClick={() => onPeriodChange(p)}>
            {p.toUpperCase()}
          </button>
        ))}
      </div>

      <StockChart
        candles={candles}
        ema9={indicators.ema9}
        ema21={indicators.ema21}
        bbUpper={indicators.bb_upper}
        bbLower={indicators.bb_lower}
        bbMid={indicators.bb_mid}
        rsi={indicators.rsi}
        macd={indicators.macd}
        macdSignal={indicators.macd_signal}
        macdHist={indicators.macd_hist}
      />

      <h3 style={{ fontSize: "0.85rem", marginBottom: 12, color: "var(--muted)" }}>Indicator breakdown</h3>
      <div className="indicator-grid">
        {signal.indicators.map((ind) => (
          <div key={ind.name} className="indicator-card">
            <div className="ind-name">{ind.name}</div>
            <div className={`ind-signal action-pill ${ind.signal === "NEUTRAL" ? "HOLD" : ind.signal}`}>
              {ind.signal}
            </div>
            <div className="ind-detail">{ind.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

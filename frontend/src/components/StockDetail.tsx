import type { StockDetail } from "../api";
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

      <div className={`signal-banner ${bannerClass(signal.action, signal.can_earn)}`}>
        <h3>{signal.can_earn ? "Buy signal — short-term trade plan" : "Market signal"}</h3>
        <p>{signal.summary}</p>
      </div>

      {signal.trade_plan && (
        <div className="trade-plan-card">
          <h3>Your trade levels</h3>
          <div className="trade-levels">
            <div className="trade-level buy-level">
              <span className="level-label">Buy at</span>
              <span className="level-price">
                {quote.currency === "INR" ? "₹" : "$"}
                {signal.trade_plan.entry_price.toLocaleString()}
              </span>
            </div>
            <div className="trade-level target-level">
              <span className="level-label">Sell target</span>
              <span className="level-price">
                {quote.currency === "INR" ? "₹" : "$"}
                {signal.trade_plan.sell_target.toLocaleString()}
              </span>
              <span className="level-pct">+{signal.trade_plan.target_pct}%</span>
            </div>
            <div className="trade-level stop-level">
              <span className="level-label">Stop loss</span>
              <span className="level-price">
                {quote.currency === "INR" ? "₹" : "$"}
                {signal.trade_plan.stop_loss.toLocaleString()}
              </span>
              <span className="level-pct">−{signal.trade_plan.stop_pct}%</span>
            </div>
          </div>
          <p className="trade-plan-note">
            Targets use ATR (average daily price range). Hold up to {signal.trade_plan.hold_days} days.
            Saved to <strong>History</strong> tab — we track if target or stop was hit.
          </p>
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

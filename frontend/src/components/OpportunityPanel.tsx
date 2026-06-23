import type { Market, StockSignal } from "../api";
import { currencyForMarket } from "../api";

interface Props {
  opportunities: StockSignal[];
  market: Market;
  onSelect: (symbol: string, market: Market) => void;
}

function fmt(n: number, market: Market) {
  const sym = currencyForMarket(market);
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function OpportunityPanel({ opportunities, market, onSelect }: Props) {
  if (opportunities.length === 0) return null;

  return (
    <div className="opportunities">
      <h2>
        {market === "US" ? "US" : "Indian"} buy signals — short-term trades ({opportunities.length})
      </h2>
      <div className="opportunity-cards">
        {opportunities.map((opp) => (
          <div
            key={`${opp.market || market}:${opp.symbol}`}
            className="opp-card"
            onClick={() => onSelect(opp.symbol, opp.market || market)}
          >
            <div className="sym">{opp.symbol}</div>
            <div className="action">{opp.action.replace("_", " ")} · {opp.confidence}% confidence</div>
            {opp.trade_plan && (
              <div className="opp-levels">
                <div><strong>Buy:</strong> {fmt(opp.trade_plan.entry_price, opp.market || market)}</div>
                <div className="target-text">
                  <strong>Sell target:</strong> {fmt(opp.trade_plan.sell_target, opp.market || market)} (+{opp.trade_plan.target_pct}%)
                </div>
                <div className="stop-text">
                  <strong>Stop loss:</strong> {fmt(opp.trade_plan.stop_loss, opp.market || market)} (−{opp.trade_plan.stop_pct}%)
                </div>
              </div>
            )}
            <div className="summary">{opp.summary}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

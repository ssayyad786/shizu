import type { StockSignal } from "../api";

interface Props {
  opportunities: StockSignal[];
  onSelect: (symbol: string) => void;
}

function fmt(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function OpportunityPanel({ opportunities, onSelect }: Props) {
  if (opportunities.length === 0) return null;

  return (
    <div className="opportunities">
      <h2>Buy signals — short-term trades ({opportunities.length})</h2>
      <div className="opportunity-cards">
        {opportunities.map((opp) => (
          <div key={opp.symbol} className="opp-card" onClick={() => onSelect(opp.symbol)}>
            <div className="sym">{opp.symbol}</div>
            <div className="action">{opp.action.replace("_", " ")} · {opp.confidence}% confidence</div>
            {opp.trade_plan && (
              <div className="opp-levels">
                <div><strong>Buy:</strong> {fmt(opp.trade_plan.entry_price)}</div>
                <div className="target-text"><strong>Sell target:</strong> {fmt(opp.trade_plan.sell_target)} (+{opp.trade_plan.target_pct}%)</div>
                <div className="stop-text"><strong>Stop loss:</strong> {fmt(opp.trade_plan.stop_loss)} (−{opp.trade_plan.stop_pct}%)</div>
              </div>
            )}
            <div className="summary">{opp.summary}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

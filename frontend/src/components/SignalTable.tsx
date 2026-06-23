import type { Market, StockSignal } from "../api";
import { currencyForMarket } from "../api";

interface Props {
  signals: StockSignal[];
  market: Market;
  selectedSymbol: string | null;
  onSelect: (symbol: string, market: Market) => void;
}

function fmtPrice(price: number, market: Market) {
  if (price <= 0) return "—";
  const sym = currencyForMarket(market);
  return `${sym}${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function SignalTable({ signals, market, selectedSymbol, onSelect }: Props) {
  if (signals.length === 0) {
    return (
      <div className="empty-state">
        <h2>No signals yet</h2>
        <p>Add stocks to your {market === "US" ? "US" : "Indian"} wishlist to start monitoring.</p>
      </div>
    );
  }

  return (
    <table className="signal-table">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Price</th>
          <th>Signal</th>
          <th>Score</th>
          <th>Confidence</th>
          <th>Summary</th>
        </tr>
      </thead>
      <tbody>
        {signals.map((s) => {
          const rowMarket = s.market || market;
          return (
            <tr
              key={`${rowMarket}:${s.symbol}`}
              onClick={() => onSelect(s.symbol, rowMarket)}
              style={{ background: selectedSymbol === s.symbol ? "var(--surface-2)" : undefined }}
            >
              <td style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{s.symbol}</td>
              <td>{fmtPrice(s.price, rowMarket)}</td>
              <td>
                <span className={`action-pill ${s.action}`}>{s.action.replace("_", " ")}</span>
              </td>
              <td style={{ fontFamily: "var(--mono)" }}>{s.score.toFixed(2)}</td>
              <td>{s.confidence}%</td>
              <td style={{ color: "var(--muted)", fontSize: "0.85rem", maxWidth: 300 }}>{s.summary}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

import type { StockSignal } from "../api";

interface Props {
  signals: StockSignal[];
  selectedSymbol: string | null;
  onSelect: (symbol: string) => void;
}

export default function SignalTable({ signals, selectedSymbol, onSelect }: Props) {
  if (signals.length === 0) {
    return (
      <div className="empty-state">
        <h2>No signals yet</h2>
        <p>Add stocks to your wishlist to start monitoring.</p>
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
        {signals.map((s) => (
          <tr
            key={s.symbol}
            onClick={() => onSelect(s.symbol)}
            style={{ background: selectedSymbol === s.symbol ? "var(--surface-2)" : undefined }}
          >
            <td style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{s.symbol}</td>
            <td>{s.price > 0 ? s.price.toFixed(2) : "—"}</td>
            <td>
              <span className={`action-pill ${s.action}`}>{s.action.replace("_", " ")}</span>
            </td>
            <td style={{ fontFamily: "var(--mono)" }}>{s.score.toFixed(2)}</td>
            <td>{s.confidence}%</td>
            <td style={{ color: "var(--muted)", fontSize: "0.85rem", maxWidth: 300 }}>{s.summary}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

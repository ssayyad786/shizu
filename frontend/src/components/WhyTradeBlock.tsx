import type { IntradayTradeReason } from "../api";

interface Props {
  headline?: string;
  reasons?: IntradayTradeReason[];
  fallbackBullets?: string[];
}

function biasClass(bias: string) {
  if (bias === "BULLISH") return "bias-bull";
  if (bias === "BEARISH") return "bias-bear";
  return "bias-neutral";
}

export default function WhyTradeBlock({ headline, reasons, fallbackBullets }: Props) {
  const hasStructured = reasons && reasons.length > 0;

  if (!headline && !hasStructured && (!fallbackBullets || fallbackBullets.length === 0)) {
    return null;
  }

  return (
    <div className="why-trade-block">
      <h4 className="why-trade-title">Why this trade</h4>
      {headline && <p className="why-trade-headline">{headline}</p>}
      {hasStructured ? (
        <ul className="why-trade-list">
          {reasons.map((r, i) => (
            <li key={i} className="why-trade-item">
              <div className="why-trade-item-header">
                <span className="why-trade-factor">{r.factor}</span>
                <span className="why-trade-weight">{r.weight}</span>
                <span className={`why-trade-bias ${biasClass(r.bias)}`}>{r.bias}</span>
              </div>
              <p className="why-trade-detail">{r.detail}</p>
            </li>
          ))}
        </ul>
      ) : (
        fallbackBullets &&
        fallbackBullets.length > 0 && (
          <ul className="intraday-reasoning">
            {fallbackBullets.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

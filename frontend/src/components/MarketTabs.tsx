import { Market, WishlistItem } from "../api";

const MARKETS: { id: Market; label: string; flag: string }[] = [
  { id: "US", label: "US", flag: "🇺🇸" },
  { id: "IN", label: "India", flag: "🇮🇳" },
];

interface Props {
  activeMarket: Market;
  wishlist: WishlistItem[];
  onChange: (market: Market) => void;
  compact?: boolean;
  counts?: Partial<Record<Market, number>>;
}

export default function MarketTabs({ activeMarket, wishlist, onChange, compact, counts }: Props) {
  const countFor = (m: Market) =>
    counts?.[m] ?? wishlist.filter((w) => w.market === m).length;
  return (
    <div className={`market-tabs ${compact ? "market-tabs-compact" : ""}`} role="tablist" aria-label="Market">
      {MARKETS.map((m) => (
        <button
          key={m.id}
          type="button"
          role="tab"
          aria-selected={activeMarket === m.id}
          className={`market-tab ${activeMarket === m.id ? "active" : ""}`}
          onClick={() => onChange(m.id)}
        >
          {m.flag} {m.label}
          <span className="market-count">{countFor(m.id)}</span>
        </button>
      ))}
    </div>
  );
}

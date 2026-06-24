import { Market, WishlistItem } from "../api";
import BrandMark from "./BrandMark";
import MarketTabs from "./MarketTabs";
import ViewModeToggle, { ViewMode } from "./ViewModeToggle";

interface Props {
  activeMarket: Market;
  wishlist: WishlistItem[];
  onMarketChange: (market: Market) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}

export default function MobileToolbar({
  activeMarket,
  wishlist,
  onMarketChange,
  viewMode,
  onViewModeChange,
}: Props) {
  return (
    <div className="mobile-toolbar">
      <BrandMark tagline="Market Monitor" size="sm" />
      <MarketTabs
        activeMarket={activeMarket}
        wishlist={wishlist}
        onChange={onMarketChange}
        compact
      />
      <ViewModeToggle mode={viewMode} onChange={onViewModeChange} compact />
    </div>
  );
}

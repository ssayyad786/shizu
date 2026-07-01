const INDICATORS = [
  {
    name: "RSI (Relative Strength Index)",
    weight: "14%",
    what: "Measures whether a stock is overbought or oversold on a 0–100 scale.",
    buy: "Below 30 = oversold (potential bounce). Below 40 = leaning bullish.",
    sell: "Above 70 = overbought (potential pullback). Above 60 = leaning bearish.",
    chart: "RSI panel — orange line with 30/70 zone markers.",
  },
  {
    name: "MACD",
    weight: "18%",
    what: "Tracks momentum by comparing two moving averages of price.",
    buy: "MACD line crosses above the signal line — momentum turning up.",
    sell: "MACD line crosses below the signal line — momentum turning down.",
    chart: "MACD panel — blue line, orange signal, green/red histogram.",
  },
  {
    name: "EMA 9 / 21 Crossover",
    weight: "18%",
    what: "Compares a fast 9-day EMA with a slower 21-day EMA to spot short-term trend changes.",
    buy: "Golden cross — EMA 9 crosses above EMA 21 (uptrend starting).",
    sell: "Death cross — EMA 9 crosses below EMA 21 (downtrend starting).",
    chart: "Price chart — blue (EMA 9) and purple (EMA 21).",
  },
  {
    name: "Bollinger Bands",
    weight: "12%",
    what: "A price channel based on 20-day average ± 2 standard deviations.",
    buy: "Price near the lower band — may be undervalued and due for a bounce.",
    sell: "Price near the upper band — may be stretched and due for a pullback.",
    chart: "Price chart — grey dashed upper/lower bands.",
  },
  {
    name: "Volume",
    weight: "12%",
    what: "Compares today's trading volume to the 20-day average.",
    buy: "Volume 1.5× above average on an up day — buying pressure confirms the move.",
    sell: "Volume 1.5× above average on a down day — selling pressure confirms the move.",
    chart: "Volume panel — green/red bars at the bottom.",
  },
  {
    name: "Stochastic Oscillator",
    weight: "14%",
    what: "Short-term momentum — where price sits within recent high/low range (0–100).",
    buy: "Below 20 = oversold. Extra bullish if %K crosses above %D while oversold.",
    sell: "Above 80 = overbought. Extra bearish if %K crosses below %D while overbought.",
    chart: "Used in scoring; shown in indicator breakdown on stock detail.",
  },
  {
    name: "ADX (Average Directional Index)",
    weight: "12%",
    what: "Measures trend strength (not direction). Above 25 = strong trend.",
    buy: "ADX > 25 with +DI above -DI — strong uptrend in play.",
    sell: "ADX > 25 with -DI above +DI — strong downtrend in play.",
    chart: "Used in scoring; filters weak/choppy markets when ADX < 20.",
  },
];

const SIGNALS = [
  {
    action: "STRONG BUY",
    desc: "Score ≥ 0.45. Sell target = entry + 2× ATR. Trade plan issued only if target is reachable within 10 trading days; saved to History.",
  },
  {
    action: "BUY",
    desc: "Score ≥ 0.20. Sell target = entry + 1.5× ATR. Same achievability rule — no target or History entry if it would take more than 10 trading days.",
  },
  {
    action: "HOLD",
    desc: "Score between −0.20 and +0.20, or bullish score but target not achievable in 10 trading days. No trade saved.",
  },
  { action: "SELL", desc: "Score ≤ −0.20 — bearish lean. Outlook shows expected downside/support range." },
  { action: "STRONG SELL", desc: "Score ≤ −0.45 — strongly bearish." },
];

const INTRADAY_TECH = [
  { label: "Model", value: "ORB + VWAP playbook — 15-minute Opening Range Breakout with VWAP alignment & volume confirmation" },
  { label: "Data source", value: "Yahoo Finance via yfinance (free delayed quotes — not Level II)" },
  { label: "Chart type", value: "OHLC candlesticks on 5m and 15m bars" },
  { label: "Timeframes", value: "Daily (trend filter) · 15m (EMA) · 5m (ORB entry & volume)" },
  { label: "Opening range", value: "First 15 minutes (9:30–9:45 AM ET) high/low — industry-standard ORB window" },
  { label: "Entry window", value: "9:45 AM–2:30 PM ET — breakouts & retests only; no late-day entries" },
  { label: "Scan frequency", value: "Every 2 minutes while US market is open (Mon–Fri)" },
  { label: "Volume rule", value: "Breakout ≥1.15× 20-bar avg; retest/continuation ≥1.05×; gap-up chase blocked" },
  { label: "VWAP rule", value: "Long only above session VWAP; short only below (institutional fair-value filter)" },
  { label: "Algo report", value: "Download report (JSON/CSV) on the Intraday tab — trade history & factor breakdown" },
  { label: "Replay backtest", value: "Pick symbol + date → reruns current ORB rules on Yahoo 5m/15m history" },
  { label: "Engine", value: "Rule-based ORB playbook (not ML) — Python + pandas + ta" },
  { label: "Stops & targets", value: "Stop at opposite side of 15m OR (min 1.25× ATR or 0.30%); T1 = 1.5R, T2 = 2.5R" },
];

const INTRADAY_FACTORS = [
  {
    name: "Opening range (ORB)",
    weight: "35%",
    what: "15-minute high/low from 9:30–9:45 ET. Core signal: candle close beyond range with volume.",
    long: "Close above OR high on a bullish bar (breakout), retest at OR high, or VWAP continuation.",
    short: "Close below OR low on a bearish bar, with retest entries near broken OR low.",
  },
  {
    name: "VWAP alignment",
    weight: "25%",
    what: "Session VWAP — where institutions judge fair price. Required for every trade.",
    long: "Price above VWAP (not extended >0.85%).",
    short: "Price below VWAP (not extended >0.85%).",
  },
  {
    name: "Breakout volume",
    weight: "20%",
    what: "Current 5m bar volume vs average volume of the three opening-range bars.",
    long: "≥ 1.2× OR average on breakout bar (up bar).",
    short: "≥ 1.2× OR average on breakout bar (down bar).",
  },
  {
    name: "EMA 9 / 20 stack",
    weight: "10%",
    what: "Short-term trend on 15m chart — micro-trend confirmation.",
    long: "Price > EMA9 > EMA20.",
    short: "Price < EMA9 < EMA20.",
  },
  {
    name: "Daily trend (21 EMA)",
    weight: "10%",
    what: "Higher-timeframe bias — avoids worst counter-trend ORB fades.",
    long: "Daily not bearish (bullish or neutral OK).",
    short: "Daily bearish required (price below 21-day EMA).",
  },
];

const INTRADAY_SIGNALS = [
  {
    action: "LONG",
    desc: "ORB breakout or retest above 15m range high, price above VWAP, volume ≥1.2×, daily not bearish. One trade/symbol/day.",
  },
  {
    action: "SHORT",
    desc: "Bearish daily required. ORB breakout/retest below range low, below VWAP, volume confirmed. Until 2:30 PM ET.",
  },
  {
    action: "HOLD",
    desc: "Inside opening range, VWAP misaligned, weak volume, or daily trend opposes direction.",
  },
];

export default function HelpPanel() {
  return (
    <div className="help-panel">
      <section className="help-section">
        <h2>About Shizu</h2>
        <div className="help-card">
          <p className="help-what">
            <strong>Shizu</strong> (Shizu Market Monitor) watches your US and Indian stock wishlists,
            scores each symbol with seven technical indicators, and highlights short-term buy opportunities
            when the math supports a clear edge. The app scans automatically every <strong>5 minutes</strong>;
            the dashboard refreshes every <strong>30 seconds</strong>.
          </p>
          <p className="help-chart">
            <strong>Dashboard</strong> — swing trades (1–10 trading days), buy cards, charts.
            <br />
            <strong>Intraday</strong> — US same-day setups (VWAP, structure, RVOL); today&apos;s trades on top.
            <br />
            <strong>My Holdings</strong> — stocks you already own; sell/hold advice with price levels and P&amp;L vs your average cost.
            <br />
            <strong>History</strong> — saved buy signals with entry, target, stop, and win/loss outcomes.
            <br />
            <strong>Help</strong> — this guide.
          </p>
        </div>
      </section>

      <section className="help-section help-disclaimer">
        <h2>Important disclaimer</h2>
        <div className="help-card help-card-disclaimer">
          <p className="help-what">
            Shizu is a <strong>learning and research tool</strong>. It is not a brokerage, does not place
            orders, and does not provide financial, investment, or tax advice. Signals come from public
            market data (Yahoo Finance) and may be wrong or delayed.{" "}
            <strong>Always do your own research</strong> before investing.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>How Shizu analyzes stocks</h2>
        <p>
          Shizu uses a <strong>multi-indicator scoring system</strong> tuned for
          <strong> short-term swing ideas (up to 10 trading days)</strong>. Seven indicators are weighted
          and combined into a single score. When a buy is valid, we set entry, sell target, and stop loss
          from <strong>ATR</strong> (average true range — typical daily price movement).
        </p>
        <p style={{ marginTop: 12 }}>
          On each stock&apos;s detail view, the <strong>market signal</strong> box explains{" "}
          <em>why</em> we say BUY, HOLD, or SELL, plus an expected upper/lower price range from
          Bollinger Bands and ATR.
        </p>
      </section>

      <section className="help-section">
        <h2>US Intraday — technology &amp; model</h2>
        <p style={{ marginBottom: 12 }}>
          The <strong>Intraday</strong> tab uses an <strong>ORB + VWAP playbook</strong> — the same approach
          used by institutional day traders: mark the first 15 minutes, trade breakouts only when price aligns
          with session VWAP and volume confirms. Each trade card shows <strong>&quot;Why this trade&quot;</strong>{" "}
          with ORB, VWAP, volume, EMA, and daily trend.
        </p>
        <table className="help-table help-tech-table">
          <tbody>
            {INTRADAY_TECH.map((row) => (
              <tr key={row.label}>
                <th>{row.label}</th>
                <td>{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ marginTop: 16, marginBottom: 8 }}>
          <strong>Not included yet</strong> (requires paid data or ML pipeline): footprint charts, volume profile,
          Level II / order flow, Heikin Ashi execution layer, XGBoost/LSTM models.
        </p>
      </section>

      <section className="help-section">
        <h2>Intraday scoring factors</h2>
        <p style={{ marginBottom: 12 }}>
          Five factors power the <strong>ORB + VWAP playbook</strong>. A valid trade needs a 15-minute opening
          range break (or retest), VWAP alignment, volume ≥1.2× the OR average, and daily trend not opposing.
          Score ≥ 0.35 and confidence ≥ 50% required.
        </p>
        <div className="help-grid">
          {INTRADAY_FACTORS.map((f) => (
            <article key={f.name} className="help-card help-card-intraday">
              <div className="help-card-header">
                <h3>{f.name}</h3>
                <span className="help-weight">Weight: {f.weight}</span>
              </div>
              <p className="help-what">{f.what}</p>
              <div className="help-signals">
                <div>
                  <span className="action-pill LONG">LONG</span>
                  <span>{f.long}</span>
                </div>
                <div>
                  <span className="action-pill SHORT">SHORT</span>
                  <span>{f.short}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="help-section">
        <h2>Intraday signal meanings</h2>
        <table className="help-table">
          <thead>
            <tr>
              <th>Signal</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            {INTRADAY_SIGNALS.map((s) => (
              <tr key={s.action}>
                <td>
                  <span className={`action-pill ${s.action}`}>{s.action}</span>
                </td>
                <td>{s.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ marginTop: 12 }}>
          Intraday history and win-rate stats stay on the <strong>Intraday tab only</strong> — not mixed with
          swing History. <strong>Today&apos;s trades</strong> appear at the top when a setup is found.
        </p>
      </section>

      <section className="help-section">
        <h2>My Holdings (sell / hold)</h2>
        <div className="help-card">
          <p className="help-what">
            Use the <strong>My Holdings</strong> tab for positions you already hold. Search by company name
            or ticker (same autocomplete as the wishlist). Enter your <strong>average purchase price</strong>
            (required); optionally add <strong>shares</strong> and <strong>purchase date</strong> for P&amp;L.
          </p>
          <p className="help-chart">
            Shizu runs the <strong>same seven-indicator model</strong> as the dashboard. For owners we map
            the signal to <strong>SELL</strong> (bearish score) or <strong>HOLD</strong> (neutral or bullish).
            Each card shows current price, your avg cost, unrealized P&amp;L, upside target, and support/stop
            zone from Bollinger Bands and ATR. Holdings are scanned every <strong>5 minutes</strong> with the
            wishlist. Nothing is saved to History — that tab is for new buy ideas only.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>US vs Indian markets</h2>
        <div className="help-card">
          <p className="help-what">
            Use the <strong>US</strong> or <strong>India</strong> tabs in the sidebar to maintain separate wishlists.
            Indian stocks use NSE/BSE symbols with a <strong>.NS</strong> or <strong>.BO</strong> suffix
            (e.g. <code>RELIANCE.NS</code>, <code>TCS.NS</code>). US stocks use plain tickers
            (e.g. <code>AAPL</code>, <code>MSFT</code>). You can paste comma-separated lists to bulk-import.
          </p>
          <p className="help-chart">
            <strong>History</strong> is split by market. Success counts only when the sell target is hit
            inside the estimated trading-day window for that signal.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>Trade plan &amp; trading-day window</h2>
        <div className="help-card">
          <p className="help-what">
            <strong>Buy at:</strong> last close when the signal fires.<br />
            <strong>Sell target:</strong> entry + 1.5× ATR (BUY) or 2× ATR (STRONG BUY).<br />
            <strong>Stop loss:</strong> entry − 1.25× ATR (minimum 0.30% from entry).<br />
            <strong>Hold period:</strong> Shizu estimates how many <strong>trading days</strong> (Mon–Fri,
            not calendar days) price needs to reach the target — based on recent up-day pace and ATR.
            The window is <strong>1–10 trading days</strong> and shown on each buy card (e.g. &quot;~4 trading days&quot;).
          </p>
          <p className="help-chart">
            <strong>Target only if achievable:</strong> if the ATR target would need more than 10 trading
            days, Shizu shows <strong>HOLD</strong> instead — no sell target, no stop, nothing saved to History.
            Outcome checks use the <strong>latest price</strong> for open trades. History lists{" "}
            <strong>30 signals per page</strong> (load more for older rows). Closed trade cards are kept for{" "}
            <strong>30 days</strong> after they close; aggregate win/loss stats are kept permanently.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>Indicators we use</h2>
        <div className="help-grid">
          {INDICATORS.map((ind) => (
            <article key={ind.name} className="help-card">
              <div className="help-card-header">
                <h3>{ind.name}</h3>
                <span className="help-weight">Weight: {ind.weight}</span>
              </div>
              <p className="help-what">{ind.what}</p>
              <div className="help-signals">
                <div>
                  <span className="action-pill BUY">BUY</span>
                  <span>{ind.buy}</span>
                </div>
                <div>
                  <span className="action-pill SELL">SELL</span>
                  <span>{ind.sell}</span>
                </div>
              </div>
              <p className="help-chart">{ind.chart}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="help-section">
        <h2>Signal meanings</h2>
        <table className="help-table">
          <thead>
            <tr>
              <th>Signal</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            {SIGNALS.map((s) => (
              <tr key={s.action}>
                <td>
                  <span className={`action-pill ${s.action.replace(" ", "_")}`}>{s.action}</span>
                </td>
                <td>{s.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="help-section help-disclaimer">
        <h2>Remember</h2>
        <p>
          Shizu is for monitoring and education — <strong>not financial advice</strong>. Past signal
          accuracy in History does not guarantee future results. Exchange holidays are not modeled in the
          trading-day window (weekdays only).
        </p>
      </section>
    </div>
  );
}

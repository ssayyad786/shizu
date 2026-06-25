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
            <strong>Dashboard</strong> — live signals, buy cards, stock table, and charts when you click a symbol.
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
            <strong>Stop loss:</strong> entry − 1× ATR.<br />
            <strong>Hold period:</strong> Shizu estimates how many <strong>trading days</strong> (Mon–Fri,
            not calendar days) price needs to reach the target — based on recent up-day pace and ATR.
            The window is <strong>1–10 trading days</strong> and shown on each buy card (e.g. &quot;~4 trading days&quot;).
          </p>
          <p className="help-chart">
            <strong>Target only if achievable:</strong> if the ATR target would need more than 10 trading
            days, Shizu shows <strong>HOLD</strong> instead — no sell target, no stop, nothing saved to History.
            Outcome checks in History start from the <strong>next trading day</strong> for daily bars,
            and also use the <strong>latest price</strong> so same-day target hits count once the signal exists.
            A trade is <strong>successful</strong> only if the sell target is hit before the window ends.
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

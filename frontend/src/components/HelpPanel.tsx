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
  { action: "STRONG BUY", desc: "Score ≥ 0.45 — target = entry + 2× ATR if reachable within 10 trading days." },
  { action: "BUY", desc: "Score ≥ 0.20 — saved to History only if target is reachable within 10 trading days." },
  { action: "HOLD", desc: "Score between −0.20 and +0.20 — no trade saved." },
  { action: "SELL", desc: "Score ≤ −0.20 — bearish lean." },
  { action: "STRONG SELL", desc: "Score ≤ −0.45 — strongly bearish." },
];

export default function HelpPanel() {
  return (
    <div className="help-panel">
      <section className="help-section help-disclaimer">
        <h2>Important disclaimer</h2>
        <div className="help-card help-card-disclaimer">
          <p className="help-what">
            Shizu is a <strong>learning and research tool</strong>. It is not a brokerage, not a trading
            platform, and does not provide financial, investment, or tax advice. All signals are generated
            automatically from public market data and may be wrong or outdated.{" "}
            <strong>Always do your own research</strong> and consult a qualified professional before
            investing.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>How we analyze stocks</h2>
        <p>
          Market Monitor uses a <strong>multi-indicator scoring system</strong> tuned for
          <strong> short-term ideas (up to 10 trading days)</strong>. Seven indicators are combined into a
          weighted score. When a BUY signal fires, we estimate entry, sell target, and stop loss using
          ATR (average daily price range).
        </p>
      </section>

      <section className="help-section">
        <h2>US vs Indian markets</h2>
        <div className="help-card">
          <p className="help-what">
            Use the <strong>US</strong> or <strong>India</strong> tab in the sidebar to maintain separate wishlists.
            Indian stocks use NSE/BSE symbols with a <strong>.NS</strong> or <strong>.BO</strong> suffix
            (e.g. <code>RELIANCE.NS</code>, <code>TCS.NS</code>). US stocks use plain tickers
            (e.g. <code>AAPL</code>, <code>MSFT</code>).
          </p>
          <p className="help-chart">
            The <strong>History</strong> tab also splits by market. Success stats only count trades where
            the sell target was hit inside the hold window.
          </p>
        </div>
      </section>

      <section className="help-section">
        <h2>Trade plan (sell target & stop loss)</h2>
        <div className="help-card">
          <p className="help-what">
            <strong>Buy at:</strong> current price when the signal fires.<br />
            <strong>Sell target:</strong> entry + 1.5× ATR (BUY) or 2× ATR (STRONG BUY).<br />
            <strong>Stop loss:</strong> entry − 1× ATR (limits loss if wrong).<br />
            <strong>Hold period:</strong> estimated trading days to reach target (1–10, weekdays only) —
            based on recent price pace and ATR. No target is issued if it would take more than 10 trading days.
            Outcome checks start from the <strong>next trading day</strong> (daily data).
          </p>
          <p className="help-chart">
            All buy signals are saved in the <strong>History</strong> tab per market. A trade is
            <strong> successful</strong> only if the sell target is hit before the window ends.
            Stop loss, or expiry without target, is not counted as success.
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
        <h2>Important</h2>
        <p>
          This tool is for monitoring and education only — <strong>not financial advice</strong>.
          Past signal accuracy does not guarantee future results. Always do your own research before trading.
        </p>
      </section>
    </div>
  );
}

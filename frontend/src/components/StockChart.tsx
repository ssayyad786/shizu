import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  IChartApi,
  CandlestickData,
  LineData,
  HistogramData,
  Time,
} from "lightweight-charts";
import type { Candle } from "../api";

const LIGHT = {
  bg: "#ffffff",
  text: "#64748b",
  grid: "#f1f5f9",
  border: "#e2e8f0",
};

interface Props {
  candles: Candle[];
  ema9: (number | null)[];
  ema21: (number | null)[];
  bbUpper: (number | null)[];
  bbLower: (number | null)[];
  bbMid: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macdSignal: (number | null)[];
  macdHist: (number | null)[];
}

function toLineData(values: (number | null)[], candles: Candle[]): LineData[] {
  const out: LineData[] = [];
  values.forEach((val, i) => {
    if (val !== null && candles[i]) {
      out.push({ time: candles[i].time as Time, value: val });
    }
  });
  return out;
}

function syncTimeScales(charts: IChartApi[]) {
  charts.forEach((chart, i) => {
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (!range) return;
      charts.forEach((other, j) => {
        if (i !== j) other.timeScale().setVisibleLogicalRange(range);
      });
    });
  });
}

export default function StockChart({
  candles,
  ema9,
  ema21,
  bbUpper,
  bbLower,
  bbMid,
  rsi,
  macd,
  macdSignal,
  macdHist,
}: Props) {
  const priceRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const volRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!priceRef.current || !rsiRef.current || !macdRef.current || !volRef.current || candles.length === 0) {
      return;
    }

    const baseOpts = {
      layout: {
        background: { type: ColorType.Solid, color: LIGHT.bg },
        textColor: LIGHT.text,
      },
      grid: {
        vertLines: { color: LIGHT.grid },
        horzLines: { color: LIGHT.grid },
      },
      crosshair: { mode: 1 as const },
      rightPriceScale: { borderColor: LIGHT.border },
      timeScale: { borderColor: LIGHT.border },
    };

    const priceChart = createChart(priceRef.current, {
      ...baseOpts,
      width: priceRef.current.clientWidth,
      height: 340,
    });

    const candleSeries = priceChart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderUpColor: "#16a34a",
      borderDownColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });
    candleSeries.setData(
      candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })) as CandlestickData[],
    );

    priceChart.addLineSeries({ color: "#2563eb", lineWidth: 2, title: "EMA 9" }).setData(toLineData(ema9, candles));
    priceChart.addLineSeries({ color: "#7c3aed", lineWidth: 2, title: "EMA 21" }).setData(toLineData(ema21, candles));
    priceChart.addLineSeries({ color: "#94a3b8", lineWidth: 1, lineStyle: 2, title: "BB Upper" }).setData(toLineData(bbUpper, candles));
    priceChart.addLineSeries({ color: "#94a3b8", lineWidth: 1, lineStyle: 2, title: "BB Lower" }).setData(toLineData(bbLower, candles));
    priceChart.addLineSeries({ color: "#cbd5e1", lineWidth: 1, title: "BB Mid" }).setData(toLineData(bbMid, candles));

    const rsiChart = createChart(rsiRef.current, {
      ...baseOpts,
      width: rsiRef.current.clientWidth,
      height: 130,
    });
    const rsiSeries = rsiChart.addLineSeries({ color: "#d97706", lineWidth: 2, title: "RSI" });
    rsiSeries.setData(toLineData(rsi, candles));
    rsiSeries.createPriceLine({ price: 70, color: "#fca5a5", lineWidth: 1, lineStyle: 2, title: "Overbought 70" });
    rsiSeries.createPriceLine({ price: 30, color: "#86efac", lineWidth: 1, lineStyle: 2, title: "Oversold 30" });

    const macdChart = createChart(macdRef.current, {
      ...baseOpts,
      width: macdRef.current.clientWidth,
      height: 130,
    });
    const histSeries = macdChart.addHistogramSeries({ title: "Histogram" });
    const histData: HistogramData[] = [];
    macdHist.forEach((val, i) => {
      if (val !== null && candles[i]) {
        histData.push({
          time: candles[i].time as Time,
          value: val,
          color: val >= 0 ? "rgba(22, 163, 74, 0.5)" : "rgba(220, 38, 38, 0.5)",
        });
      }
    });
    histSeries.setData(histData);
    macdChart.addLineSeries({ color: "#2563eb", lineWidth: 2, title: "MACD" }).setData(toLineData(macd, candles));
    macdChart.addLineSeries({ color: "#f59e0b", lineWidth: 2, title: "Signal" }).setData(toLineData(macdSignal, candles));

    const volChart = createChart(volRef.current, {
      ...baseOpts,
      width: volRef.current.clientWidth,
      height: 90,
    });
    const volSeries = volChart.addHistogramSeries({ title: "Volume" });
    volSeries.setData(
      candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(22, 163, 74, 0.45)" : "rgba(220, 38, 38, 0.45)",
      })),
    );

    const charts = [priceChart, rsiChart, macdChart, volChart];
    charts.forEach((c) => c.timeScale().fitContent());
    syncTimeScales(charts);

    const onResize = () => {
      if (priceRef.current) priceChart.applyOptions({ width: priceRef.current.clientWidth });
      if (rsiRef.current) rsiChart.applyOptions({ width: rsiRef.current.clientWidth });
      if (macdRef.current) macdChart.applyOptions({ width: macdRef.current.clientWidth });
      if (volRef.current) volChart.applyOptions({ width: volRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      priceChart.remove();
      rsiChart.remove();
      macdChart.remove();
      volChart.remove();
    };
  }, [candles, ema9, ema21, bbUpper, bbLower, bbMid, rsi, macd, macdSignal, macdHist]);

  return (
    <div className="charts-stack">
      <div className="chart-legend">
        <span className="legend-item"><i style={{ background: "#16a34a" }} /> Green candle = price went up</span>
        <span className="legend-item"><i style={{ background: "#dc2626" }} /> Red candle = price went down</span>
        <span className="legend-item"><i style={{ background: "#2563eb" }} /> EMA 9 — fast trend line</span>
        <span className="legend-item"><i style={{ background: "#7c3aed" }} /> EMA 21 — slow trend line</span>
        <span className="legend-item"><i style={{ background: "#94a3b8" }} /> Bollinger Bands — price channel (grey dashed)</span>
      </div>

      <div className="chart-panel">
        <div className="chart-panel-label">
          <strong>Price chart</strong>
          <span>Candlesticks show open/high/low/close. When blue EMA 9 crosses above purple EMA 21, trend may be turning up.</span>
        </div>
        <div ref={priceRef} className="chart-wrapper" />
      </div>

      <div className="chart-panel">
        <div className="chart-panel-label">
          <strong>RSI (14)</strong>
          <span>Below 30 = oversold (may bounce up). Above 70 = overbought (may pull back). Green/red dashed lines mark those zones.</span>
        </div>
        <div ref={rsiRef} className="chart-wrapper chart-wrapper-sm" />
      </div>

      <div className="chart-panel">
        <div className="chart-panel-label">
          <strong>MACD</strong>
          <span>Blue line crossing above orange signal = bullish momentum. Bars (histogram) show strength of the move.</span>
        </div>
        <div ref={macdRef} className="chart-wrapper chart-wrapper-sm" />
      </div>

      <div className="chart-panel">
        <div className="chart-panel-label">
          <strong>Volume</strong>
          <span>Taller bars = more shares traded. Big volume on a green day confirms buyers; on a red day confirms sellers.</span>
        </div>
        <div ref={volRef} className="chart-wrapper chart-wrapper-xs" />
      </div>
    </div>
  );
}

# Quantitative Trading & Market Analysis Portfolio

A collection of quantitative research projects built with Python: systematic strategy backtesting, machine-learning direction prediction, and interactive market dashboards.

**Live dashboards:** <https://catherine313-oops.github.io/AI-quant/>

## Projects

| Project | Type | Entry file |
| --- | --- | --- |
| Turtle Trading Strategy | Systematic strategy + backtest | `gold-turtle-strategy.html` |
| ML Trading Strategy | Classification + backtest | `strategy_report.html` |
| ML Classification Notebook | Modelling code | `ml-trading-strategy.html` |
| Financial Market Analysis | Exploratory visualisation | `smic-market-analysis.html`, `moutai-market-analysis.html`, `maotai_close_price.html`, `gold-price-analysis.html` |

---

## 1. Turtle Trading Strategy

### Overview

A systematic trend-following strategy that applies the classic Turtle rules — Donchian Channel breakout entries with ATR-based position sizing and trailing stops — to a 10-year daily series of Shandong Gold (600547.SH), benchmarked against buy-and-hold.

### Methodology

- **Data** — Daily OHLCV for 600547.SH from Tushare Pro, 2016-07-13 to 2026-07-13 (10 years).
- **Indicators** — 20-day Donchian Channel (upper / middle / lower), 14-day ATR.
- **Strategy** — Long when close breaks above the upper channel; exit when close breaks below the lower channel. Initial stop at entry − 2×ATR, ratcheted to close − 2×ATR whenever it rises (trailing stop). Long-only, one position at a time.
- **Position sizing** — Risk 2% of equity per trade; shares = risk ÷ (2 × ATR), rounded down to a lot of 100.
- **Backtesting** — Event-driven daily loop over the full series. Initial capital ¥100,000; commission 0.03% and slippage 0.1% per trade; open positions closed at the final bar.

### Results

| Metric | Value |
| --- | --- |
| Total return (10y) | +6.85% |
| Annualised return | +0.66% |
| Max drawdown | −17.76% |
| Sharpe ratio (rf = 2.5%) | −0.203 |
| Win rate | 36.5% (19W / 33L) |
| Trades | 52 |
| Profit factor | 1.13 |
| Annualised volatility | 7.51% |
| Buy-and-hold | −49.95% |

The strategy beat buy-and-hold by roughly 57 percentage points, mostly by staying flat through large drawdowns.

### Limitations

- Long-only, single instrument, single parameter set — no walk-forward or out-of-sample validation.
- Absolute return is modest and the Sharpe ratio is negative once a 2.5% risk-free rate is subtracted.
- Costs are modelled simplistically; no taxes, no liquidity or position-limit constraints.
- One stock in one market — the result is not evidence that the rule generalises.

### Future Improvements

- Walk-forward / rolling-window parameter selection to reduce overfitting.
- Portfolio-level application across several instruments with correlated exposure control.
- A market-regime filter to cut whipsaw losses in sideways markets.
- Benchmark against volatility-targeted buy-and-hold rather than the naive version.

---

## 2. Machine Learning Trading Strategy

### Overview

An end-to-end study of whether machine-learning classifiers can predict the next-day direction of a Chinese gold equity (600547.SH, Shandong Gold), and whether the resulting signal is tradable after costs.

### Methodology

- **Data** — Daily OHLCV from Tushare Pro, 2,398 bars (2016-07-18 to 2026-07-17). The modelling notebook splits 2016–2023 train / 2024–2025 test.
- **Label** — Binary: 1 if next close > today's close, else 0 (built with `shift(-1)`).
- **Features** — Basic derived features only: returns, intraday range, volume change, rolling statistics, calendar features. No external or alternative data.
- **Models** — Logistic Regression, Decision Tree, Random Forest, Gradient Boosting, XGBoost; compared by 5-fold cross-validation and test AUC. Selected model: Logistic Regression (AUC 0.5407).
- **Strategy** — Buy when predicted probability > 0.55, exit when < 0.45.
- **Backtesting** — Daily backtest with costs, benchmarked against buy-and-hold. An extended version adds a three-model ensemble (LR + RF + XGBoost), regression forecasts of the 5-day return, dual-signal confirmation, and volatility-adaptive position sizing (capped at 1.5×).

### Results

Baseline (Logistic Regression):

| Metric | Value |
| --- | --- |
| Total return | +12.80% |
| Annualised return | +6.45% |
| Max drawdown | −20.55% |
| Sharpe ratio | 0.292 |
| Sortino ratio | 0.351 |
| Win rate | 54.3% |
| Trades | 35 |
| Profit factor | 1.23 |
| Buy-and-hold | −8.10% |
| Excess return | +20.90% |

Model comparison (test set): accuracy across all five models sits in a narrow 48%–52% band, AUC 0.497–0.541 — only marginally above a coin flip.

Ensemble + adaptive-sizing version: −6.32% total return vs −17.62% buy-and-hold (+11.31% excess), max drawdown −12.76%, Sharpe −0.353, 18 trades.

### Limitations

- Predictive power is weak in absolute terms — accuracy 48%–52%, AUC ≈ 0.54. This is the honest headline result, and the report says so explicitly.
- Single instrument, single feature set, one train/test split; no walk-forward validation and no multiple-testing correction across models.
- The more complex ensemble version produced a worse absolute return than the simple baseline.
- Costs, slippage and market impact are modelled only approximately.
- The value captured is defensive (avoiding drawdowns) rather than directional — the strategy lags buy-and-hold in strong up-quarters.

### Future Improvements

- Walk-forward evaluation across several rolling windows instead of a single split.
- Enrich features with cross-asset signals (gold futures, USD index, VIX, sector indices).
- Cost sensitivity analysis and a break-even cost level for the signal.
- Test the signal as a risk-off overlay rather than a standalone directional strategy.

---

## 3. Financial Market Analysis

### Overview

Interactive exploratory dashboards for three A-share instruments, built to practise time-series handling, technical indicators and data visualisation.

### Methodology

- **Data** — Daily OHLCV from Tushare Pro: SMIC (688981.SH), 236 trading days to 2026-07-03; Kweichow Moutai (600519.SH), 242 trading days to 2026-07-06; Huaan Gold ETF (518880.SH), 50 trading days to 2026-07-06.
- **Indicators** — Daily returns, MA5 / MA20 with interactive parameter control, golden / death cross detection, monthly return and volume aggregation, distribution of daily returns.
- **Analysis** — Candlestick charts with volume, monthly performance tables, return-distribution histograms, and a click-to-mark paper-trading mode that computes return, win rate and max drawdown from user-marked entries and exits.
- **Tooling** — Python for data preparation, ECharts for rendering. Chinese market colour convention throughout (red = up, green = down).

### Results

- SMIC (688981.SH): +63.53% over the period (¥85.80 → ¥140.31); high ¥166.88, low ¥84.86; largest single-day move +18.78%.
- Kweichow Moutai (600519.SH): latest close ¥1,194.45; period high ¥1,555.00, low ¥1,168.63.
- Huaan Gold ETF (518880.SH): −13.72% over the period; MA5 ¥8.485 below MA20 ¥8.646.

### Limitations

- Descriptive analysis only — no predictive modelling, no significance testing.
- Short windows (50–242 trading days); conclusions do not generalise beyond the sample.
- Dashboards are static HTML snapshots refreshed by a scheduled workflow, not live.

### Future Improvements

- Extend the sample to multiple years and benchmark against a market index.
- Add drawdown, rolling volatility and cross-asset correlation panels.
- Replace remaining hard-coded summary figures with values computed from the embedded data.

---

## Repository Layout

```
index.html                            portfolio hub (GitHub Pages entry)
gold-turtle-strategy.html             Turtle strategy dashboard
update_dashboard.py            daily data + backtest script
strategy_report.html       ML strategy backtest report
ml-trading-strategy.html  ML modelling notebook (HTML export)
smic-market-analysis.html             SMIC dashboard
moutai-market-analysis.html           Moutai dashboard
maotai_close_price.html      Moutai close-price dashboard
gold-price-analysis.html              Gold ETF dashboard
```

*For learning and research purposes only. Not investment advice.*

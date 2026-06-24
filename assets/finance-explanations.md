# Finance Explanations

A plain-language reference for every metric Market Horizon shows. The goal is simple: you should
never see a number like `RSI = 72` without being able to understand what it means, how it was
produced, and how to read it sensibly.

> **Important — informational only.** Market Horizon does not produce trading recommendations,
> price forecasts, or buy/sell signals. Every metric below describes *what has already happened* in
> the stored daily price history. Nothing here is financial advice.

## How to read this document

Each indicator follows the same structure:

- **What it is** — the concept in one or two sentences.
- **How it is calculated** — the exact method used in the app.
- **How to read it** — sensible interpretation.
- **Strengths / Limitations** — when it helps and when it can mislead.
- **Example** — a concrete illustration.

### Conventions used everywhere

- All metrics are computed on **daily** data using the **adjusted close** when available (it
  accounts for dividends and splits), otherwise the raw close.
- "Observations" means trading days, not calendar days. Roughly: 1 month ≈ 21 observations,
  3 months ≈ 63, 1 year ≈ 252.
- When there is **not enough stored history** to compute a metric honestly, the app shows
  `Unavailable` rather than a misleading value.

---

## Returns

Returns measure percentage price change over a period. They answer: *how has the asset performed?*

### 1 Day Return

- **What it is:** Percentage change versus the previous trading day.
- **How it is calculated:** `close[today] / close[yesterday] − 1`.
- **How to read it:** Short-term move. Naturally noisy — a single day says little on its own.
- **Example:** Close yesterday `100`, close today `101` → **+1.00%**.

### 1 Month Return

- **What it is:** Change compared to roughly one month ago.
- **How it is calculated:** Return over the last **21 observations**.
- **How to read it:** Recent momentum, less noisy than a single day.

### 3 Month Return

- **What it is:** Change over roughly a quarter.
- **How it is calculated:** Return over the last **63 observations**.
- **How to read it:** A good lens on medium-term momentum.

### YTD (Year to Date)

- **What it is:** Performance since the first trading day of the current calendar year.
- **How it is calculated:** `close[latest] / close[first close on/after Jan 1] − 1`.
- **How to read it:** "How is this asset doing this year?" Comparable across assets within the
  same year, but the lookback window shrinks/grows depending on the date.

### 1 Year Return

- **What it is:** Longer-term performance.
- **How it is calculated:** Return over the last **252 observations**.
- **How to read it:** A broad sense of the trajectory over the past year.

> **Limitation for all returns:** they are *point-to-point*. Two assets with the same 1Y return can
> have travelled very different, more or less volatile, paths to get there.

---

## Trend Indicators (Moving Averages)

Moving averages smooth out daily noise to reveal direction. In the Asset Analysis chart the
**adjusted close is the only solid line**; each moving average is drawn with its own dashed style
and colour so they are easy to tell apart.

### EMA 20 — Exponential Moving Average (20)

- **What it is:** A 20-observation average that gives **more weight to recent prices**, so it
  reacts quickly to change.
- **How it is calculated:** Exponentially weighted mean with a span of 20 (needs ≥20 observations).
- **How to read it:** Proxy for the **short-term** trend.
  - Price **above** EMA 20 → short-term strength.
  - Price **below** EMA 20 → short-term weakness.
- **Strengths:** Responsive; good for spotting shifts early.
- **Limitations:** Responsiveness cuts both ways — more false turns in choppy markets.
- **Chart colour:** purple, dashed.

### SMA 50 — Simple Moving Average (50)

- **What it is:** The unweighted average of the last 50 closes.
- **How it is calculated:** Rolling mean over 50 observations (needs ≥50).
- **How to read it:** Proxy for the **medium-term** trend.
- **Strengths:** Smoother and steadier than EMA 20.
- **Limitations:** Lags real turning points because every day is weighted equally.
- **Chart colour:** amber, dotted.

### SMA 200 — Simple Moving Average (200)

- **What it is:** The unweighted average of the last 200 closes.
- **How it is calculated:** Rolling mean over 200 observations (needs ≥200).
- **How to read it:** The classic gauge of the **long-term** direction.
- **Strengths:** Very stable; filters out short-term noise.
- **Limitations:** Slow to react; needs a lot of history (often `Unavailable` for newer assets).
- **Chart colour:** azure/sky blue, dash-dot.

---

## Momentum

### RSI 14 — Relative Strength Index

- **What it is:** A 0–100 oscillator measuring the **speed and size** of recent gains versus losses.
- **How it is calculated:** Over 14 observations, the average gain is divided by the average loss to
  form `RS`, then `RSI = 100 − 100 / (1 + RS)`. Higher RSI = recent gains have dominated.
- **How to read it:**

  ```text
  0 ───── 30 ───── 70 ───── 100
     Oversold   Neutral   Overbought
  ```

  - Below 30 → recent selling pressure has been strong ("oversold").
  - 30–70 → neutral / balanced.
  - Above 70 → recent buying pressure has been strong ("overbought").
- **Educational note:** Overbought does **not** mean "sell" and oversold does **not** mean "buy".
  Strong assets can stay overbought for a long time. RSI describes the recent past, not the future.
- **Example:** `RSI = 72` → recent gains have outweighed losses; momentum has been strong lately.

---

## Risk

### Volatility (annualized)

- **What it is:** How much daily returns fluctuate — a measure of uncertainty, not of direction.
- **How it is calculated:** Standard deviation of daily returns over a window, scaled to a yearly
  figure by multiplying by `√(periods per year)`. The annualization factor is **252** for
  stocks/ETFs and **365** for crypto (crypto trades every day). The app reports a short-window
  (30-observation) and a longer-window (90-observation) reading; the watchlist column uses a
  1-year (252-observation) window.
- **How to read it:** Higher = larger swings = more uncertainty. Lower = steadier behaviour.
- **Limitations:** It treats up-moves and down-moves the same, and assumes recent behaviour is
  representative — which is not always true.
- **Example:**

  ```text
  Broad-market ETF   ≈ 15% annualized volatility
  Bitcoin            ≈ 65% annualized volatility
  ```

### 52 Week Drawdown

- **What it is:** How far the current price sits **below its highest point of the last ~52 weeks**.
- **How it is calculated:** `current price / max(price over last 252 observations) − 1`. It is zero
  or negative by construction.
- **How to read it:** A quick read on "how far off its recent peak is this?"
- **Example:**

  ```text
  52W High = 100
  Current  =  80   →   Drawdown = −20%
  ```

### Maximum Drawdown

- **What it is:** The **largest peak-to-trough decline** anywhere in the stored history.
- **How it is calculated:** The minimum of `price / running_peak − 1` across the whole series.
- **How to read it:** Answers "what was the worst historical decline an investor would have sat
  through?" — a tangible sense of downside.
- **Limitations:** Backward-looking; the worst future decline can always exceed the worst past one.

---

## Range Position

### 52 Week Range Position

- **What it is:** Where today's price sits **inside** its 52-week low–high band.
- **How it is calculated:** `(current − 52W low) / (52W high − 52W low)`, expressed 0–100%.
- **How to read it:**

  ```text
  0%    near the yearly low
  50%   middle of the range
  100%  near the yearly high
  ```
- **Limitation:** Position alone says nothing about *why* — context (trend, volatility) matters.

---

## Trend Classification

This is the heart of Market Horizon's methodology, and it is deliberately transparent: instead of a
mysterious score, each horizon is labelled **Positive**, **Negative**, or **Mixed**.

Each horizon combines three transparent facts:

| Horizon      | Moving average | Performance reference |
| ------------ | -------------- | --------------------- |
| Short term   | EMA 20         | 1 month return        |
| Medium term  | SMA 50         | 3 month return        |
| Long term    | SMA 200        | 1 year return         |

The label is decided as follows:

- **Positive** — price is **above** the moving average **and** the moving average is **rising**
  **and** the period performance is **positive**. All three agree on strength.
- **Negative** — price is **below** the moving average **and** the moving average is **falling**
  **and** the period performance is **negative**. All three agree on weakness.
- **Mixed** — the signals disagree (e.g. price is above a falling average). Honest ambiguity.
- **Unavailable** — not enough stored history to judge this horizon.

Why three separate horizons? So you can see at a glance whether the short-term move **agrees** with
the medium- and long-term picture, which is often more informative than any single number.

> **Reminder:** a "Positive" label is a description of recent, observed behaviour across price and
> its moving average — not a prediction and not a recommendation.

---

## Frequently asked

**Why do some metrics say `Unavailable`?**
The asset does not yet have enough stored daily history for that calculation (for example, SMA 200
needs at least 200 trading days). The app prefers to show nothing rather than a misleading value.

**Why adjusted close instead of raw close?**
Adjusted close incorporates dividends and stock splits, so percentage changes reflect what an
investor actually experienced rather than artificial jumps on split/dividend days.

**Why 252 vs 365 for volatility?**
Stocks and ETFs trade ~252 days a year; crypto trades every day. Using the right factor keeps
annualized volatility comparable and meaningful per asset type.

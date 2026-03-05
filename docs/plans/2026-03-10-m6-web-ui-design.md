# M6: Web UI — Design

Dashboard for monitoring the autoresearch system, running portfolio analysis, and inspecting experiments. Generated via v0, backed by FastAPI.

## Decisions

| Decision | Choice |
|---|---|
| Frontend generation | v0 scaffold, customize locally |
| Frontend framework | Next.js 14 App Router + Tailwind + shadcn/ui + Recharts |
| Backend API | FastAPI wrapping existing Python modules |
| Data connection | Next.js fetches from FastAPI (`:3000` → `:8000`) |
| Portfolio analysis | Triggerable from UI via POST endpoint |
| Loop control | Start/stop from UI (FastAPI manages subprocess) |
| Pages | Dashboard, Portfolio Analysis, Experiment Detail |

## Architecture

```
frontend/ (Next.js, v0-generated)
    ↕ fetch JSON
src/api/server.py (FastAPI, port 8000)
    ↕ Python imports
Existing core (Storage, PortfolioAnalyst, ResearchLoop, etc.)
```

- FastAPI is a thin read layer + two action endpoints (analyze, loop start/stop)
- Research loop runs as subprocess managed by FastAPI (PID tracking, SIGINT for stop)
- CORS enabled for dev; prod behind reverse proxy

## FastAPI Endpoints

### Read (GET)

| Endpoint | Returns | Wraps |
|---|---|---|
| `/api/strategy/current` | current strategy config + metrics | `Storage.get_latest_strategy_version()` + YAML load |
| `/api/strategy/history` | all strategy versions | `Storage.get_strategy_versions()` |
| `/api/experiments?last=N` | recent experiments | `Storage.get_recent_experiments()` |
| `/api/experiments/{id}` | single experiment detail | `Storage.get_experiment()` |
| `/api/experiments/{id}/paper-trades` | paper trading snapshots | `Storage.get_paper_trades()` |
| `/api/scores/{ticker}?last=N` | score history for ticker | DB query |
| `/api/loop/status` | loop state | `Storage.get_loop_state()` + process alive check |

### Action (POST)

| Endpoint | Action | Wraps |
|---|---|---|
| `POST /api/analyze` `{tickers, days?}` | run portfolio analysis | `PortfolioAnalyst.analyze()` |
| `POST /api/loop/start` `{tickers, days?, cooldown?}` | start research loop subprocess | `subprocess.Popen(research.py)` |
| `POST /api/loop/stop` | SIGINT to loop subprocess | `os.kill(pid, SIGINT)` |

## Pages

### Dashboard (`/`)
- Current strategy card: version badge, Sharpe, CAGR, max drawdown, win rate
- Research loop card: status badge, consecutive rejections progress bar, paper trading status, start/stop controls with ticker input
- Recent experiments table: ID, hypothesis, decision badge, Sharpe delta, date. Clickable rows → experiment detail. Paginated.

### Portfolio Analysis (`/analyze`)
- Ticker input + timeframe select + Analyze button (loading state)
- Results table: rank, ticker, action badge, composite score progress bar, confidence, per-signal scores
- Risk warnings as alert cards

### Experiment Detail (`/experiments/[id]`)
- Header: experiment ID, decision badge, hypothesis, parent version, date
- Config changes card: diff display with green/red highlights
- Metrics comparison table: baseline vs experiment with colored deltas
- Validation gates: 2x3 grid of pass/fail cards with detail text
- Paper trading chart: two-line cumulative return comparison (Recharts)
- Decision card: badge + reasoning narrative

## v0 Prompt

```
Build a quantitative trading research dashboard using Next.js 14 App Router, Tailwind CSS, and shadcn/ui components throughout. Use Recharts for charts. Dark mode by default. All data is placeholder — API will be wired later.

Layout:
- Sidebar navigation using shadcn NavigationMenu or custom sidebar: links for "Dashboard", "Analyze", "Experiments". Show app name "Quant Autoresearch" at top of sidebar with a small chart icon. Sidebar is collapsible. Bottom of sidebar: dark/light mode toggle using shadcn Switch.
- Main content area with consistent padding and max-width.

Page 1 — Dashboard (/)

Top row — two shadcn Card components side by side:

"Current Strategy" card:
- Card header: title "Current Strategy" with a shadcn Badge showing version "v0.2"
- Card content: 4-column grid of stats, each with a muted label above and large bold number below:
  - Sharpe: "1.24"
  - CAGR: "18.3%"
  - Max Drawdown: "12.1%"
  - Win Rate: "62%"
- Card footer: small muted text "Promoted 2026-03-08"

"Research Loop" card:
- Card header: title "Research Loop" with a shadcn Badge variant — green "Running", yellow "Paused", or destructive "Stopped"
- Card content: stats row showing "Consecutive Rejections: 3/10" with a shadcn Progress bar, and "Paper Trading: exp-007 (day 6/10)" or "None"
- Card footer: a row with shadcn Input (placeholder "AAPL, MSFT, GOOG..."), shadcn Button variant="default" "Start", shadcn Button variant="destructive" "Stop"

Below cards — shadcn Card with title "Recent Experiments":
- shadcn Table with columns: ID, Hypothesis, Decision, Sharpe Δ, Date
- Decision column uses shadcn Badge: variant="default" green for "promoted", variant="destructive" for "rejected", variant="outline" yellow text for "paper_testing", variant="secondary" for "invalidated"
- Sharpe Δ column shows "+0.15" in green or "-0.08" in red text
- 10 rows of realistic placeholder data about strategy changes (e.g., "increase trend weight to 0.40", "tighten sell threshold to 45")
- Rows have hover state and are clickable (navigate to /experiments/[id])
- Below table: shadcn Pagination component

Page 2 — Portfolio Analysis (/analyze)

Top section — shadcn Card:
- Title "Portfolio Analysis"
- Row: shadcn Input (large, placeholder "Enter tickers: AAPL, NVDA, MSFT, AMD..."), shadcn Select for timeframe (options: "1 Year", "2 Years", "3 Years"), shadcn Button "Analyze" with a play icon
- When loading: replace button text with shadcn Spinner and "Analyzing..."

Results section (visible after analysis) — shadcn Card:
- Title "Results — Strategy v0.2" with subtitle showing analysis date
- shadcn Table with columns:
  - Rank (#)
  - Ticker (bold, monospace)
  - Action: shadcn Badge — green "BUY", muted "HOLD", destructive "SELL"
  - Score: shadcn Progress bar (0-100) with number label, colored green >70, yellow 40-70, red <40
  - Confidence: percentage
  - Trend: small number
  - Rel Str: small number
  - Volatility: small number
  - Liquidity: small number
- 8 rows of realistic placeholder data for tech stocks
- Each signal sub-score column has subtle background tinting: green for high scores, red for low

Below table — conditional "Risk Warnings" section:
- Uses shadcn Alert variant="warning" for each warning
- Example warnings: "Sector concentration: 62% Technology (max 40%)", "Borderline score: AMD at 69 (buy threshold: 70)"

Page 3 — Experiment Detail (/experiments/[id])

Breadcrumb: Dashboard > Experiments > exp-007

Header row:
- Large title "exp-007" with shadcn Badge showing decision (promoted/rejected/paper_testing)
- Subtitle: the hypothesis text in muted italic
- Small muted text: "Parent: v0.1 | Created: 2026-03-08"

Two-column grid below header:

Left column — "Config Changes" card:
- Show the config diff in a styled code block using shadcn formatting
- Format like: weights.trend: 0.35 → 0.40, weights.fundamentals: 0.20 → 0.15
- Changed values highlighted with green/red background

Right column — "Metrics Comparison" card:
- shadcn Table with 3 columns: Metric, Baseline, Experiment
- Rows: Sharpe, CAGR, Max Drawdown, Hit Rate, Monthly Turnover
- Experiment column values colored green if better, red if worse
- Delta column showing the difference

Below — "Validation Gates" card:
- 2x3 grid of mini cards, one per gate: Sharpe, Walk-Forward, Drawdown, Turnover, Regime Diversity, Paper Trading
- Each shows: gate name, large pass/fail icon (green checkmark or red X), detail text below in muted small text
- Example: "Walk-Forward" with green check and "Won 4/4 windows (100%)"

Below — "Paper Trading" card (only shown if experiment is/was paper_testing):
- Recharts LineChart with two lines: "Baseline" (muted/dashed) and "Experiment" (solid blue/green)
- X-axis: days (Day 1–10), Y-axis: cumulative return %
- Below chart: stats row — "Days: 6/10", "Beat Baseline: Yes", "Directional Consistency: 70%"
- If still in progress, show a shadcn Progress bar for days completed

Bottom — "Decision" card:
- Large shadcn Badge with decision
- Below: the reasoning narrative text in a prose block
- If promoted: "Promoted to v0.2 on 2026-03-09" with a link
```

## Files

```
src/api/
├── server.py          # FastAPI app
├── routes/
│   ├── strategy.py    # /api/strategy/* endpoints
│   ├── experiments.py # /api/experiments/* endpoints
│   ├── analyze.py     # POST /api/analyze
│   ├── loop.py        # /api/loop/* endpoints
│   └── scores.py      # /api/scores/* endpoints
frontend/              # v0-generated Next.js app
├── app/
│   ├── page.tsx       # Dashboard
│   ├── analyze/
│   │   └── page.tsx   # Portfolio Analysis
│   └── experiments/
│       └── [id]/
│           └── page.tsx # Experiment Detail
├── components/        # v0-generated shadcn components
└── lib/
    └── api.ts         # API client helpers
```

## Unresolved Questions
- Deployment: run both processes manually for now, or use docker-compose?

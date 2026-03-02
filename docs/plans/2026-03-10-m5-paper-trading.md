# M5: Paper Trading + Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement shadow portfolio paper trading gate and operational hardening (crash recovery, graceful shutdown, logging) for the research loop.

**Architecture:** New `paper_trader.py` tracks shadow portfolios daily. Promoter gains `"paper_testing"` state. Loop checks paper trading progress each iteration and resolves after 10 days. `loop_state` table enables crash recovery. SIGINT handler enables graceful shutdown.

**Tech Stack:** Python 3.12+, DuckDB (existing Storage), Alpaca (existing provider), logging (stdlib)

---

### Task 1: DB — paper_trades + loop_state tables

**Files:**
- Modify: `src/data/db.py`
- Create: `tests/test_db_paper_trading.py`

**Step 1: Write the failing test**

```python
# tests/test_db_paper_trading.py
import pytest
from datetime import datetime, date
from src.data.db import Storage


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def test_store_and_get_paper_trade(db):
    db.store_paper_trade(
        experiment_id="exp-001",
        trade_date=date(2026, 3, 1),
        baseline_positions={"AAPL": "buy", "MSFT": "hold"},
        experiment_positions={"AAPL": "buy", "MSFT": "buy"},
        baseline_return=0.01,
        experiment_return=0.015,
        baseline_cumulative=0.01,
        experiment_cumulative=0.015,
    )
    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 1
    assert trades[0]["experiment_id"] == "exp-001"
    assert trades[0]["experiment_return"] == 0.015


def test_get_paper_trades_empty(db):
    trades = db.get_paper_trades("exp-999")
    assert trades == []


def test_paper_trade_count(db):
    for i in range(5):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.01, experiment_return=0.02,
            baseline_cumulative=0.01 * (i + 1), experiment_cumulative=0.02 * (i + 1),
        )
    assert db.get_paper_trade_count("exp-001") == 5
    assert db.get_paper_trade_count("exp-999") == 0


def test_store_and_get_loop_state(db):
    db.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 3, 1),
        consecutive_rejections=3,
    )
    state = db.get_loop_state()
    assert state is not None
    assert state["status"] == "running"
    assert state["paper_trading_experiment"] == "exp-001"
    assert state["consecutive_rejections"] == 3


def test_update_loop_state(db):
    db.save_loop_state(status="running", consecutive_rejections=0)
    db.save_loop_state(status="paused", consecutive_rejections=10)
    state = db.get_loop_state()
    assert state["status"] == "paused"
    assert state["consecutive_rejections"] == 10


def test_get_loop_state_empty(db):
    state = db.get_loop_state()
    assert state is None


def test_invalidate_inflight_experiments(db):
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "hyp 1")
    db.update_experiment_decision("exp-001", "rejected", {})
    db.store_experiment("exp-002", "0.1", {"weights": {"trend": 0.35}}, "hyp 2")
    # exp-002 has no decision yet (in-flight)
    db.store_experiment("exp-003", "0.1", {"weights": {"trend": 0.30}}, "hyp 3")
    db.update_experiment_decision("exp-003", "paper_testing", {})

    db.invalidate_inflight_experiments(exclude_id="exp-003")
    exp2 = db.get_experiment("exp-002")
    assert exp2["decision"] == "invalidated"
    # exp-001 already had a decision, should be unchanged
    exp1 = db.get_experiment("exp-001")
    assert exp1["decision"] == "rejected"
    # exp-003 was excluded
    exp3 = db.get_experiment("exp-003")
    assert exp3["decision"] == "paper_testing"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_paper_trading.py -v`
Expected: FAIL — methods don't exist

**Step 3: Write minimal implementation**

Add to `src/data/db.py` in `_init_tables()`:

```python
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                experiment_id VARCHAR,
                trade_date DATE,
                baseline_positions JSON,
                experiment_positions JSON,
                baseline_return DOUBLE,
                experiment_return DOUBLE,
                baseline_cumulative DOUBLE,
                experiment_cumulative DOUBLE,
                PRIMARY KEY (experiment_id, trade_date)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS loop_state (
                loop_id VARCHAR PRIMARY KEY DEFAULT 'main',
                status VARCHAR,
                paper_trading_experiment VARCHAR,
                paper_start_date DATE,
                last_iteration_at TIMESTAMP,
                consecutive_rejections INTEGER DEFAULT 0
            )
        """)
```

Add methods to `Storage` class:

```python
    def store_paper_trade(self, experiment_id: str, trade_date, baseline_positions: dict,
                          experiment_positions: dict, baseline_return: float,
                          experiment_return: float, baseline_cumulative: float,
                          experiment_cumulative: float):
        self.conn.execute(
            "INSERT OR REPLACE INTO paper_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [experiment_id, trade_date, json.dumps(baseline_positions),
             json.dumps(experiment_positions), baseline_return, experiment_return,
             baseline_cumulative, experiment_cumulative]
        )

    def get_paper_trades(self, experiment_id: str) -> list[dict]:
        df = self.conn.execute(
            "SELECT * FROM paper_trades WHERE experiment_id = ? ORDER BY trade_date",
            [experiment_id]
        ).fetchdf()
        if df.empty:
            return []
        return df.to_dict("records")

    def get_paper_trade_count(self, experiment_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE experiment_id = ?",
            [experiment_id]
        ).fetchone()[0]

    def save_loop_state(self, status: str, paper_trading_experiment: str | None = None,
                        paper_start_date=None, consecutive_rejections: int = 0):
        self.conn.execute(
            """INSERT OR REPLACE INTO loop_state
               VALUES ('main', ?, ?, ?, ?, ?)""",
            [status, paper_trading_experiment, paper_start_date,
             datetime.now(), consecutive_rejections]
        )

    def get_loop_state(self) -> dict | None:
        df = self.conn.execute(
            "SELECT * FROM loop_state WHERE loop_id = 'main'"
        ).fetchdf()
        if df.empty:
            return None
        return df.to_dict("records")[0]

    def invalidate_inflight_experiments(self, exclude_id: str | None = None):
        if exclude_id:
            self.conn.execute(
                "UPDATE experiments SET decision = 'invalidated' WHERE decision IS NULL AND experiment_id != ?",
                [exclude_id]
            )
        else:
            self.conn.execute(
                "UPDATE experiments SET decision = 'invalidated' WHERE decision IS NULL"
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_paper_trading.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add src/data/db.py tests/test_db_paper_trading.py
git commit -m "feat: paper_trades + loop_state tables and DB methods"
```

---

### Task 2: PaperTrader — shadow portfolio tracking

**Files:**
- Create: `src/research/paper_trader.py`
- Create: `tests/test_paper_trader.py`

**Step 1: Write the failing test**

```python
# tests/test_paper_trader.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime
from unittest.mock import MagicMock
from src.data.db import Storage
from src.research.paper_trader import PaperTrader


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def _make_bars(ticker: str, dates: list, closes: list) -> pd.DataFrame:
    """Helper to create bars DataFrame."""
    return pd.DataFrame({
        "symbol": [ticker] * len(dates),
        "timestamp": [pd.Timestamp(d) for d in dates],
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1000000] * len(dates),
    })


def test_record_day_computes_returns(db):
    dates = [f"2026-03-{d:02d}" for d in range(1, 12)]
    bars = {
        "AAPL": _make_bars("AAPL", dates, [100 + i for i in range(11)]),
        "MSFT": _make_bars("MSFT", dates, [200 + i * 2 for i in range(11)]),
        "SPY": _make_bars("SPY", dates, [400 + i for i in range(11)]),
    }

    # Mock runner that returns fixed positions
    baseline_runner = MagicMock()
    baseline_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 75},
        "MSFT": {"action": "hold", "composite_score": 55},
    }
    experiment_runner = MagicMock()
    experiment_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 80},
        "MSFT": {"action": "buy", "composite_score": 72},
    }

    trader = PaperTrader(
        db=db,
        experiment_id="exp-001",
        tickers=["AAPL", "MSFT"],
        bars=bars,
        baseline_runner=baseline_runner,
        experiment_runner=experiment_runner,
    )

    result = trader.record_day(date(2026, 3, 10))
    assert result is not None
    assert "baseline_return" in result
    assert "experiment_return" in result
    assert "baseline_cumulative" in result
    assert "experiment_cumulative" in result

    # Should have stored in DB
    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 1


def test_record_multiple_days_cumulative(db):
    dates = [f"2026-03-{d:02d}" for d in range(1, 15)]
    # AAPL goes up, MSFT flat
    bars = {
        "AAPL": _make_bars("AAPL", dates, [100 + i * 2 for i in range(14)]),
        "MSFT": _make_bars("MSFT", dates, [200] * 14),
        "SPY": _make_bars("SPY", dates, [400] * 14),
    }

    baseline_runner = MagicMock()
    baseline_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 75},
    }
    experiment_runner = MagicMock()
    experiment_runner.get_positions.return_value = {
        "AAPL": {"action": "buy", "composite_score": 80},
        "MSFT": {"action": "buy", "composite_score": 70},
    }

    trader = PaperTrader(
        db=db, experiment_id="exp-001", tickers=["AAPL", "MSFT"],
        bars=bars, baseline_runner=baseline_runner,
        experiment_runner=experiment_runner,
    )

    trader.record_day(date(2026, 3, 10))
    trader.record_day(date(2026, 3, 11))
    trader.record_day(date(2026, 3, 12))

    trades = db.get_paper_trades("exp-001")
    assert len(trades) == 3
    # Cumulative should be monotonically tracked
    cums = [t["experiment_cumulative"] for t in trades]
    assert len(cums) == 3


def test_evaluate_gate_pass(db):
    # Simulate 10 days where experiment beats baseline
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=0.008,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=0.008 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db, max_underperformance=0.01)
    assert result["passed"] is True
    assert result["experiment_cumulative"] > 0
    assert result["beat_baseline"] is True


def test_evaluate_gate_fail_negative_return(db):
    # Experiment has negative return
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=-0.003,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=-0.003 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db)
    assert result["passed"] is False
    assert "negative return" in result["reason"].lower()


def test_evaluate_gate_fail_underperformance(db):
    # Experiment underperforms baseline by more than 1%
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.01, experiment_return=0.005,
            baseline_cumulative=0.01 * (i + 1),
            experiment_cumulative=0.005 * (i + 1),
        )
    result = PaperTrader.evaluate_gate("exp-001", db, max_underperformance=0.01)
    assert result["passed"] is False
    assert "underperform" in result["reason"].lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_paper_trader.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write minimal implementation**

```python
# src/research/paper_trader.py
import logging
from datetime import date, datetime
import pandas as pd
from src.data.db import Storage
from src.research.runner import StrategyRunner

logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(
        self,
        db: Storage,
        experiment_id: str,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        baseline_runner: StrategyRunner,
        experiment_runner: StrategyRunner,
    ):
        self.db = db
        self.experiment_id = experiment_id
        self.tickers = tickers
        self.bars = bars
        self.baseline_runner = baseline_runner
        self.experiment_runner = experiment_runner

    def record_day(self, trade_date: date) -> dict | None:
        """Record one day of shadow portfolio tracking."""
        as_of = datetime.combine(trade_date, datetime.min.time())

        baseline_pos = self.baseline_runner.get_positions(self.tickers, self.bars, as_of)
        experiment_pos = self.experiment_runner.get_positions(self.tickers, self.bars, as_of)

        baseline_buys = [t for t, p in baseline_pos.items() if p["action"] == "buy"]
        experiment_buys = [t for t, p in experiment_pos.items() if p["action"] == "buy"]

        baseline_ret = self._daily_return(baseline_buys, trade_date)
        experiment_ret = self._daily_return(experiment_buys, trade_date)

        # Get previous cumulative
        prev_trades = self.db.get_paper_trades(self.experiment_id)
        if prev_trades:
            prev_b_cum = prev_trades[-1]["baseline_cumulative"]
            prev_e_cum = prev_trades[-1]["experiment_cumulative"]
        else:
            prev_b_cum = 0.0
            prev_e_cum = 0.0

        b_cum = prev_b_cum + baseline_ret
        e_cum = prev_e_cum + experiment_ret

        self.db.store_paper_trade(
            experiment_id=self.experiment_id,
            trade_date=trade_date,
            baseline_positions={t: p["action"] for t, p in baseline_pos.items()},
            experiment_positions={t: p["action"] for t, p in experiment_pos.items()},
            baseline_return=round(baseline_ret, 6),
            experiment_return=round(experiment_ret, 6),
            baseline_cumulative=round(b_cum, 6),
            experiment_cumulative=round(e_cum, 6),
        )

        return {
            "baseline_return": baseline_ret,
            "experiment_return": experiment_ret,
            "baseline_cumulative": b_cum,
            "experiment_cumulative": e_cum,
        }

    def _daily_return(self, buy_tickers: list[str], trade_date: date) -> float:
        """Equal-weight daily return for given tickers on trade_date."""
        if not buy_tickers:
            return 0.0

        returns = []
        for t in buy_tickers:
            df = self.bars.get(t)
            if df is None:
                continue
            mask = df["timestamp"].dt.date <= trade_date
            recent = df[mask].sort_values("timestamp").tail(2)
            if len(recent) < 2:
                continue
            prev_close = recent.iloc[-2]["close"]
            curr_close = recent.iloc[-1]["close"]
            if prev_close > 0:
                returns.append((curr_close - prev_close) / prev_close)

        if not returns:
            return 0.0
        return sum(returns) / len(returns)

    @staticmethod
    def evaluate_gate(
        experiment_id: str,
        db: Storage,
        max_underperformance: float = 0.01,
    ) -> dict:
        """Evaluate the paper trading gate after N days."""
        trades = db.get_paper_trades(experiment_id)
        if not trades:
            return {"passed": False, "reason": "No paper trades recorded"}

        last = trades[-1]
        e_cum = last["experiment_cumulative"]
        b_cum = last["baseline_cumulative"]
        n_days = len(trades)

        # Directional consistency (secondary)
        days_won = sum(1 for t in trades if t["experiment_return"] > t["baseline_return"])
        consistency = days_won / n_days if n_days > 0 else 0

        # Primary gate: non-negative AND not underperforming by >threshold
        if e_cum < 0:
            return {
                "passed": False,
                "reason": f"Negative return: experiment cumulative = {e_cum:.4f}",
                "experiment_cumulative": e_cum,
                "baseline_cumulative": b_cum,
                "beat_baseline": e_cum > b_cum,
                "directional_consistency": consistency,
                "days": n_days,
            }

        underperformance = b_cum - e_cum
        if underperformance > max_underperformance:
            return {
                "passed": False,
                "reason": f"Underperformance vs baseline: {underperformance:.4f} > {max_underperformance}",
                "experiment_cumulative": e_cum,
                "baseline_cumulative": b_cum,
                "beat_baseline": False,
                "directional_consistency": consistency,
                "days": n_days,
            }

        return {
            "passed": True,
            "reason": "Paper trading gate passed",
            "experiment_cumulative": e_cum,
            "baseline_cumulative": b_cum,
            "beat_baseline": e_cum > b_cum,
            "directional_consistency": consistency,
            "days": n_days,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_paper_trader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/research/paper_trader.py tests/test_paper_trader.py
git commit -m "feat: PaperTrader shadow portfolio tracking + gate evaluation"
```

---

### Task 3: Promoter — paper_testing decision state

**Files:**
- Modify: `src/research/promoter.py`
- Create: `tests/test_promoter_paper.py`

**Step 1: Write the failing test**

```python
# tests/test_promoter_paper.py
import pytest
from src.research.promoter import Promoter


def _all_pass_verdict():
    return {
        "overall": "pass",
        "gates": [
            {"name": "sharpe", "passed": True, "detail": "1.2 > 0.8"},
            {"name": "walk_forward", "passed": True, "detail": "4/4 windows"},
            {"name": "drawdown", "passed": True, "detail": "ok"},
            {"name": "turnover", "passed": True, "detail": "ok"},
            {"name": "regime_diversity", "passed": True, "detail": "ok"},
        ],
        "failed_gates": [],
    }


def _fail_verdict():
    return {
        "overall": "fail",
        "gates": [
            {"name": "sharpe", "passed": False, "detail": "0.5 < 0.8"},
        ],
        "failed_gates": ["sharpe"],
    }


def test_all_backtest_gates_pass_returns_paper_testing():
    promoter = Promoter()
    verdict = _all_pass_verdict()
    # Note: verdict has no paper_trading gate — backtest gates only
    result = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "paper_testing"


def test_backtest_gate_fails_returns_rejected():
    promoter = Promoter()
    verdict = _fail_verdict()
    result = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "rejected"


def test_paper_gate_pass_returns_promoted():
    promoter = Promoter()
    paper_result = {
        "passed": True,
        "experiment_cumulative": 0.05,
        "baseline_cumulative": 0.03,
        "beat_baseline": True,
        "directional_consistency": 0.7,
        "days": 10,
    }
    result = promoter.decide_paper(paper_result, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "promoted"


def test_paper_gate_fail_returns_rejected():
    promoter = Promoter()
    paper_result = {
        "passed": False,
        "reason": "Negative return",
        "experiment_cumulative": -0.02,
        "baseline_cumulative": 0.03,
        "beat_baseline": False,
        "directional_consistency": 0.3,
        "days": 10,
    }
    result = promoter.decide_paper(paper_result, "exp-001", {"weights": {"trend": 0.40}})
    assert result["decision"] == "rejected"
    assert "paper trading" in result["reasoning"].lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_promoter_paper.py -v`
Expected: FAIL — `decide_backtest` and `decide_paper` don't exist

**Step 3: Write implementation**

Replace `src/research/promoter.py`:

```python
# src/research/promoter.py
import anthropic

DECISION_PROMPT = """You are a strategy promoter for a quant autoresearch system.

An experiment has passed ALL validation gates including paper trading. Review the results and write a brief promotion rationale.

Experiment: {experiment_id}
Config changes: {config_diff}

Gate results:
{gate_details}

Paper trading results:
{paper_details}

Write 2-3 sentences explaining why this change is being promoted. Be specific about the metrics."""


class Promoter:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def decide(self, verdict: dict, experiment_id: str, config_diff: dict) -> dict:
        """Legacy method — calls decide_backtest for backwards compatibility."""
        return self.decide_backtest(verdict, experiment_id, config_diff)

    def decide_backtest(self, verdict: dict, experiment_id: str, config_diff: dict) -> dict:
        """Decide after backtest gates. Returns paper_testing or rejected."""
        if verdict["overall"] == "fail":
            failed = verdict["failed_gates"]
            gate_details = "\n".join(
                f"  {g['name']}: {'PASS' if g['passed'] else 'FAIL'} — {g['detail']}"
                for g in verdict["gates"]
            )
            return {
                "decision": "rejected",
                "reasoning": f"Auto-rejected: failed gates: {', '.join(failed)}.\n{gate_details}",
            }

        gate_details = "\n".join(
            f"  {g['name']}: PASS — {g['detail']}"
            for g in verdict["gates"]
        )
        return {
            "decision": "paper_testing",
            "reasoning": f"All backtest gates passed. Entering 10-day paper trading.\n{gate_details}",
        }

    def decide_paper(self, paper_result: dict, experiment_id: str, config_diff: dict) -> dict:
        """Decide after paper trading completes. Returns promoted or rejected."""
        if not paper_result["passed"]:
            return {
                "decision": "rejected",
                "reasoning": (
                    f"Paper trading gate failed: {paper_result.get('reason', 'unknown')}. "
                    f"Experiment cumulative: {paper_result.get('experiment_cumulative', 0):.4f}, "
                    f"Baseline cumulative: {paper_result.get('baseline_cumulative', 0):.4f}, "
                    f"Directional consistency: {paper_result.get('directional_consistency', 0):.0%}"
                ),
            }

        # Paper trading passed — call LLM for promotion narrative
        paper_details = (
            f"  Experiment cumulative return: {paper_result['experiment_cumulative']:.4f}\n"
            f"  Baseline cumulative return: {paper_result['baseline_cumulative']:.4f}\n"
            f"  Beat baseline: {paper_result['beat_baseline']}\n"
            f"  Directional consistency: {paper_result['directional_consistency']:.0%}\n"
            f"  Days: {paper_result['days']}"
        )
        prompt = DECISION_PROMPT.format(
            experiment_id=experiment_id,
            config_diff=config_diff,
            gate_details="All backtest gates passed (see experiment record)",
            paper_details=paper_details,
        )

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            reasoning = response.content[0].text
        except Exception as e:
            reasoning = (
                f"All gates + paper trading passed. Auto-promoting. (LLM unavailable: {e}). "
                f"Paper: exp={paper_result['experiment_cumulative']:.4f}, "
                f"base={paper_result['baseline_cumulative']:.4f}"
            )

        return {
            "decision": "promoted",
            "reasoning": reasoning,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_promoter_paper.py -v`
Expected: PASS

**Step 5: Run existing promoter tests to verify backwards compatibility**

Run: `pytest tests/ -k promoter -v`
Expected: All pass (legacy `decide()` method preserved)

**Step 6: Commit**

```bash
git add src/research/promoter.py tests/test_promoter_paper.py
git commit -m "feat: promoter paper_testing decision state + decide_backtest/decide_paper"
```

---

### Task 4: Auditor — remove paper trading stub

**Files:**
- Modify: `src/research/auditor.py`
- Modify: `tests/test_auditor.py` (if exists, otherwise create)

**Step 1: Write the failing test**

```python
# tests/test_auditor_no_paper_stub.py
import pytest
from src.research.auditor import evaluate_gates
from src.research.results import BacktestResult, WindowResult


def _make_result(sharpe: float, max_dd: float = 0.1, turnover: float = 0.1) -> BacktestResult:
    return BacktestResult(
        strategy_version="test",
        window_results=[
            WindowResult(window_id=i, train_start="", train_end="", test_start="", test_end="",
                         metrics={"sharpe": sharpe, "max_drawdown": max_dd, "monthly_turnover": turnover})
            for i in range(4)
        ],
        aggregate_metrics={"sharpe": sharpe, "max_drawdown": max_dd, "monthly_turnover": turnover},
    )


def test_no_paper_trading_gate_in_evaluate_gates():
    """evaluate_gates should NOT include paper_trading gate — it's handled separately now."""
    baseline = _make_result(0.5)
    experiment = _make_result(1.0)
    verdict = evaluate_gates(baseline, experiment)
    gate_names = [g["name"] for g in verdict["gates"]]
    assert "paper_trading" not in gate_names
    # Should have exactly 5 gates now
    assert len(verdict["gates"]) == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_auditor_no_paper_stub.py -v`
Expected: FAIL — paper_trading gate still present (6 gates)

**Step 3: Remove the stub from auditor.py**

In `src/research/auditor.py`, remove lines 99-104:

```python
    # Gate 6: Paper trading (stubbed — always passes in M3)
    gates.append({
        "name": "paper_trading",
        "passed": True,
        "detail": "stubbed — paper trading gate not enforced until M5",
    })
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_auditor_no_paper_stub.py -v`
Expected: PASS

**Step 5: Run all auditor tests**

Run: `pytest tests/ -k auditor -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/research/auditor.py tests/test_auditor_no_paper_stub.py
git commit -m "feat: remove paper trading stub from auditor — handled by PaperTrader now"
```

---

### Task 5: Loop — paper trading integration

**Files:**
- Modify: `src/research/loop.py`
- Create: `tests/test_loop_paper_trading.py`

**Step 1: Write the failing test**

```python
# tests/test_loop_paper_trading.py
import pytest
import pandas as pd
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from src.data.db import Storage
from src.research.loop import ResearchLoop


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def dummy_bars():
    dates = [f"2024-{m:02d}-15" for m in range(1, 25)]
    bars = {}
    for ticker in ["AAPL", "MSFT", "SPY"]:
        bars[ticker] = pd.DataFrame({
            "symbol": [ticker] * len(dates),
            "timestamp": pd.to_datetime(dates),
            "open": [100.0] * len(dates),
            "high": [105.0] * len(dates),
            "low": [95.0] * len(dates),
            "close": [100.0 + i * 0.5 for i in range(len(dates))],
            "volume": [1000000] * len(dates),
        })
    return bars


def test_loop_checks_paper_trading_on_startup(db, dummy_bars, tmp_path):
    """If an experiment is in paper_testing state on startup, loop should detect it."""
    storage = Storage(db)
    storage.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "test hyp")
    storage.update_experiment_decision("exp-001", "paper_testing", {"sharpe": 1.0})
    storage.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 2, 25),
        consecutive_rejections=0,
    )
    storage.close()

    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    loop = ResearchLoop(
        tickers=["AAPL", "MSFT"], bars=dummy_bars,
        strategies_dir=strategies_dir, db_path=db,
    )
    assert loop.paper_trading_experiment == "exp-001"
    loop.db.close()


def test_loop_saves_state_each_iteration(db, dummy_bars, tmp_path):
    """Loop should save state to DB after each iteration."""
    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    loop = ResearchLoop(
        tickers=["AAPL", "MSFT"], bars=dummy_bars,
        strategies_dir=strategies_dir, db_path=db,
    )

    # Mock proposer to return None (skip) so iteration is fast
    loop.proposer = MagicMock()
    loop.proposer.propose.return_value = None

    loop.run(max_iterations=1)

    storage = Storage(db)
    state = storage.get_loop_state()
    storage.close()
    assert state is not None
    assert state["status"] in ("running", "stopped")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_loop_paper_trading.py -v`
Expected: FAIL — `paper_trading_experiment` attribute doesn't exist

**Step 3: Update loop.py**

Replace `src/research/loop.py`:

```python
# src/research/loop.py
import time
import logging
from datetime import date, datetime
import pandas as pd
from src.data.db import Storage
from src.strategy.config import load_strategy, StrategyConfig
from src.strategy.registry import StrategyRegistry
from src.research.proposer import Proposer
from src.research.promoter import Promoter
from src.research.experiment import ExperimentManager
from src.research.auditor import evaluate_gates
from src.research.backtester import Backtester
from src.research.context import build_context_summary
from src.research.schema import validate_config_diff, apply_diff
from src.research.runner import StrategyRunner
from src.research.paper_trader import PaperTrader

logger = logging.getLogger(__name__)

PAPER_TRADING_DAYS = 10


class ResearchLoop:
    def __init__(
        self,
        tickers: list[str],
        bars: dict[str, pd.DataFrame],
        strategies_dir: str = "strategies",
        experiments_dir: str = "experiments",
        db_path: str = "data/trading_agent.duckdb",
        cooldown_seconds: int = 3600,
        max_consecutive_rejections: int = 10,
    ):
        self.tickers = tickers
        self.bars = bars
        self.db = Storage(db_path)
        self.registry = StrategyRegistry(self.db, strategies_dir)
        self.manager = ExperimentManager(self.db, experiments_dir)
        self.proposer = Proposer()
        self.promoter = Promoter()
        self.cooldown_seconds = cooldown_seconds
        self.max_consecutive_rejections = max_consecutive_rejections
        self.strategies_dir = strategies_dir
        self.shutdown_requested = False

        # Restore state from DB
        self._restore_state()

    def _restore_state(self):
        """Restore loop state from DB (crash recovery)."""
        state = self.db.get_loop_state()
        if state:
            self.consecutive_rejections = state.get("consecutive_rejections", 0)
            self.paper_trading_experiment = state.get("paper_trading_experiment")
            self.paper_start_date = state.get("paper_start_date")
            logger.info(f"Restored state: rejections={self.consecutive_rejections}, "
                        f"paper_trading={self.paper_trading_experiment}")
        else:
            self.consecutive_rejections = 0
            self.paper_trading_experiment = None
            self.paper_start_date = None

    def _save_state(self, status: str = "running"):
        """Save loop state to DB."""
        self.db.save_loop_state(
            status=status,
            paper_trading_experiment=self.paper_trading_experiment,
            paper_start_date=self.paper_start_date,
            consecutive_rejections=self.consecutive_rejections,
        )

    def run(self, max_iterations: int | None = None) -> list[dict]:
        """Run the research loop. Returns list of iteration results."""
        results = []
        iteration = 0

        while not self.shutdown_requested:
            if max_iterations and iteration >= max_iterations:
                break
            if self.consecutive_rejections >= self.max_consecutive_rejections:
                logger.info(f"Pausing: {self.consecutive_rejections} consecutive rejections")
                self._save_state(status="paused")
                break

            # Check paper trading first
            if self.paper_trading_experiment:
                paper_result = self._check_paper_trading()
                if paper_result:
                    results.append(paper_result)
                    if paper_result["decision"] == "rejected":
                        self.consecutive_rejections += 1
                    else:
                        self.consecutive_rejections = 0

            if self.shutdown_requested:
                break

            # Run normal iteration
            result = self.run_one_iteration()
            results.append(result)

            if result["decision"] == "rejected":
                self.consecutive_rejections += 1
            elif result["decision"] != "paper_testing":
                self.consecutive_rejections = 0

            self._save_state()
            iteration += 1

            if max_iterations is None and not self.shutdown_requested:
                time.sleep(self.cooldown_seconds)

        self._save_state(status="stopped")
        self.db.close()
        return results

    def _check_paper_trading(self) -> dict | None:
        """Check if paper trading experiment is ready for evaluation."""
        exp_id = self.paper_trading_experiment
        n_days = self.db.get_paper_trade_count(exp_id)

        if n_days < PAPER_TRADING_DAYS:
            # Record today's shadow portfolio
            self._record_paper_day(exp_id)
            n_days = self.db.get_paper_trade_count(exp_id)

        if n_days < PAPER_TRADING_DAYS:
            logger.info(f"Paper trading {exp_id}: {n_days}/{PAPER_TRADING_DAYS} days")
            return None

        # Evaluate gate
        gate_result = PaperTrader.evaluate_gate(exp_id, self.db)
        exp = self.db.get_experiment(exp_id)
        config_diff = exp.get("config_diff", {})
        if isinstance(config_diff, str):
            import json
            config_diff = json.loads(config_diff)

        decision = self.promoter.decide_paper(gate_result, exp_id, config_diff)

        if decision["decision"] == "promoted":
            parent_version = exp.get("parent_version", "0.1")
            new_version = self.registry.promote(
                parent_version=parent_version,
                config_diff=config_diff,
                metrics=gate_result,
            )
            decision["new_version"] = new_version
            logger.info(f"Paper trading passed — promoted {exp_id} -> v{new_version}")
            # Invalidate in-flight experiments
            self.db.invalidate_inflight_experiments(exclude_id=exp_id)
        else:
            logger.info(f"Paper trading failed — rejected {exp_id}")

        # Update experiment record
        self.db.update_experiment_decision(exp_id, decision["decision"], gate_result)

        # Clear paper trading state
        self.paper_trading_experiment = None
        self.paper_start_date = None

        return {
            "experiment_id": exp_id,
            "decision": decision["decision"],
            "metrics": gate_result,
            "phase": "paper_trading",
        }

    def _record_paper_day(self, exp_id: str):
        """Record one day of shadow portfolio for paper trading experiment."""
        exp = self.db.get_experiment(exp_id)
        if not exp:
            return

        config_diff = exp.get("config_diff", {})
        if isinstance(config_diff, str):
            import json
            config_diff = json.loads(config_diff)

        config_path = self.registry.get_current_config_path()
        baseline_config = load_strategy(config_path)
        baseline_runner = StrategyRunner(baseline_config)

        merged_dict = apply_diff(
            {"weights": baseline_config.weights, "thresholds": baseline_config.thresholds,
             "filters": baseline_config.filters},
            config_diff,
        )
        exp_config = _build_config(baseline_config, merged_dict)
        experiment_runner = StrategyRunner(exp_config)

        trader = PaperTrader(
            db=self.db, experiment_id=exp_id, tickers=self.tickers,
            bars=self.bars, baseline_runner=baseline_runner,
            experiment_runner=experiment_runner,
        )
        trader.record_day(date.today())

    def run_one_iteration(self) -> dict:
        """Run one propose-backtest-decide iteration."""
        config_path = self.registry.get_current_config_path()
        baseline_config = load_strategy(config_path)

        baseline_bt = Backtester(baseline_config)
        baseline_result = baseline_bt.run(self.tickers, self.bars)

        baseline_snapshot = {
            "weights": baseline_config.weights,
            "thresholds": baseline_config.thresholds,
            "filters": baseline_config.filters,
        }
        recent = self.db.get_recent_experiments(limit=10)
        context = build_context_summary(
            baseline_result.aggregate_metrics, baseline_snapshot, recent
        )

        proposal = self.proposer.propose(context)
        if proposal is None:
            return {"experiment_id": None, "decision": "skipped", "reason": "no valid proposal"}

        errors = validate_config_diff(baseline_snapshot, proposal["config_diff"])
        if errors:
            logger.warning(f"Invalid proposal: {errors}")
            return {"experiment_id": None, "decision": "skipped", "reason": f"invalid: {errors}"}

        exp = self.manager.create(
            parent_version=baseline_config.version,
            config_diff=proposal["config_diff"],
            hypothesis=proposal["hypothesis"],
        )

        merged_dict = apply_diff(baseline_snapshot, proposal["config_diff"])
        exp_config = _build_config(baseline_config, merged_dict)

        exp_bt = Backtester(exp_config)
        exp_result = exp_bt.run(self.tickers, self.bars)

        verdict = evaluate_gates(baseline_result, exp_result)
        decision = self.promoter.decide_backtest(verdict, exp["experiment_id"], proposal["config_diff"])

        # If paper_testing, set up paper trading
        if decision["decision"] == "paper_testing":
            if self.paper_trading_experiment:
                # Already paper trading something — discard this one
                decision["decision"] = "rejected"
                decision["reasoning"] = (
                    f"All backtest gates passed but another experiment "
                    f"({self.paper_trading_experiment}) is already paper trading. Discarded."
                )
            else:
                self.paper_trading_experiment = exp["experiment_id"]
                self.paper_start_date = date.today()
                logger.info(f"Entering paper trading: {exp['experiment_id']}")

        # Record
        self.manager.record_decision(
            exp["experiment_id"], exp["dir_name"],
            decision=decision["decision"],
            metrics=exp_result.aggregate_metrics,
            reasoning=decision["reasoning"],
        )

        return {
            "experiment_id": exp["experiment_id"],
            "decision": decision["decision"],
            "metrics": exp_result.aggregate_metrics,
            "hypothesis": proposal["hypothesis"],
        }


def _build_config(baseline_config, merged_dict):
    """Build a StrategyConfig from merged dict, preserving backtest config."""
    return StrategyConfig(
        version=f"{baseline_config.version}-exp",
        name="experiment",
        weights=merged_dict.get("weights", baseline_config.weights),
        thresholds=merged_dict.get("thresholds", baseline_config.thresholds),
        filters=merged_dict.get("filters", baseline_config.filters),
        backtest=baseline_config.backtest,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_loop_paper_trading.py -v`
Expected: PASS

**Step 5: Run all loop tests**

Run: `pytest tests/ -k loop -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/research/loop.py tests/test_loop_paper_trading.py
git commit -m "feat: loop paper trading integration — check, record, resolve, invalidate"
```

---

### Task 6: Graceful shutdown — SIGINT handler

**Files:**
- Modify: `research.py`
- Create: `tests/test_graceful_shutdown.py`

**Step 1: Write the failing test**

```python
# tests/test_graceful_shutdown.py
import pytest
import signal
import pandas as pd
from unittest.mock import MagicMock, patch
from src.research.loop import ResearchLoop
from src.data.db import Storage


def test_shutdown_flag_stops_loop(tmp_path):
    """Setting shutdown_requested stops the loop cleanly."""
    db_path = str(tmp_path / "test.duckdb")
    strategies_dir = str(tmp_path / "strategies")
    import os, shutil
    os.makedirs(strategies_dir, exist_ok=True)
    shutil.copy("strategies/v0.1.yaml", f"{strategies_dir}/v0.1.yaml")

    dates = [f"2024-{m:02d}-15" for m in range(1, 25)]
    bars = {}
    for ticker in ["AAPL", "SPY"]:
        bars[ticker] = pd.DataFrame({
            "symbol": [ticker] * len(dates),
            "timestamp": pd.to_datetime(dates),
            "open": [100.0] * len(dates),
            "high": [105.0] * len(dates),
            "low": [95.0] * len(dates),
            "close": [100.0 + i for i in range(len(dates))],
            "volume": [1000000] * len(dates),
        })

    loop = ResearchLoop(
        tickers=["AAPL"], bars=bars,
        strategies_dir=strategies_dir, db_path=db_path,
    )

    # Mock proposer so it doesn't call Anthropic
    call_count = 0
    def mock_propose(context):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            loop.shutdown_requested = True
        return None

    loop.proposer = MagicMock()
    loop.proposer.propose.side_effect = mock_propose

    results = loop.run(max_iterations=10)
    # Should stop after ~2 iterations due to shutdown flag
    assert len(results) <= 3

    # State should be saved
    storage = Storage(db_path)
    state = storage.get_loop_state()
    storage.close()
    assert state is not None
    assert state["status"] == "stopped"
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_graceful_shutdown.py -v`
Expected: PASS (loop.py already has `shutdown_requested` support from Task 5)

**Step 3: Update research.py with SIGINT handler**

Replace `research.py`:

```python
#!/usr/bin/env python3
"""Quant Autoresearch Agent — Research Loop CLI."""
import argparse
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

from src.data.alpaca import AlpacaProvider
from src.research.loop import ResearchLoop


def setup_logging(log_dir: str = "logs"):
    """Configure logging to console + rotating file."""
    Path(log_dir).mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        f"{log_dir}/research.log", maxBytes=10_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(description="Run the autoresearch loop")
    parser.add_argument("tickers", nargs="+", help="Tickers to research")
    parser.add_argument("--days", type=int, default=730, help="Days of history")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations (default: unlimited)")
    parser.add_argument("--cooldown", type=int, default=3600, help="Seconds between iterations")
    parser.add_argument("--max-rejections", type=int, default=10, help="Stop after N consecutive rejections")
    parser.add_argument("--log-dir", default="logs", help="Log directory")
    args = parser.parse_args()

    setup_logging(args.log_dir)
    logger = logging.getLogger("research")

    load_dotenv()
    for key in ["ALPACA_API_KEY", "ALPACA_SECRET", "ANTHROPIC_API_KEY"]:
        if not os.environ.get(key):
            print(f"Error: Set {key} in .env")
            sys.exit(1)

    provider = AlpacaProvider()
    tickers = [t.upper() for t in args.tickers]
    all_tickers = tickers + ["SPY"]
    end = datetime.now()
    start = end - timedelta(days=args.days)

    logger.info(f"Fetching {args.days} days of data for {len(tickers)} tickers + SPY...")
    all_bars_df = provider.get_bars(all_tickers, start, end)
    if all_bars_df.empty:
        logger.error("No data returned.")
        sys.exit(1)

    bars = {}
    for ticker in all_tickers:
        mask = all_bars_df["symbol"] == ticker
        if mask.any():
            bars[ticker] = all_bars_df[mask].sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Starting research loop (cooldown={args.cooldown}s, max_rejections={args.max_rejections})...")
    loop = ResearchLoop(
        tickers=tickers, bars=bars,
        cooldown_seconds=args.cooldown,
        max_consecutive_rejections=args.max_rejections,
    )

    # Graceful shutdown handler
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} — requesting graceful shutdown...")
        loop.shutdown_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    results = loop.run(max_iterations=args.max_iterations)

    logger.info(f"Research loop complete — {len(results)} iterations")
    print(f"\n{'='*60}")
    print(f"  Research Loop Complete — {len(results)} iterations")
    print(f"{'='*60}")
    for r in results:
        phase = f" [{r.get('phase', 'backtest')}]" if r.get("phase") else ""
        status = "+" if r["decision"] == "promoted" else "~" if r["decision"] == "paper_testing" else "-"
        print(f"  {status} {r.get('experiment_id', '?')}: {r['decision']}{phase} — {r.get('hypothesis', '')[:60]}")


if __name__ == "__main__":
    main()
```

**Step 4: Verify .gitignore includes logs/**

Run: `grep -q "logs/" .gitignore || echo "logs/" >> .gitignore`

**Step 5: Commit**

```bash
git add research.py .gitignore
git commit -m "feat: graceful shutdown (SIGINT/SIGTERM) + rotating file logging"
```

---

### Task 7: query.py — paper trading subcommand

**Files:**
- Modify: `query.py`
- Modify: `tests/test_query.py`

**Step 1: Write the failing test**

```python
# append to tests/test_query.py
import sys
from datetime import date

@pytest.fixture
def db_with_paper_trades(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    db = Storage(db_path)
    db.store_experiment("exp-001", "0.1", {"weights": {"trend": 0.40}}, "test")
    for i in range(5):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={"AAPL": "buy"}, experiment_positions={"AAPL": "buy"},
            baseline_return=0.005, experiment_return=0.008,
            baseline_cumulative=0.005 * (i + 1), experiment_cumulative=0.008 * (i + 1),
        )
    db.close()
    yield db_path


def test_paper_trades_query(db_with_paper_trades):
    result = subprocess.run(
        [sys.executable, "query.py", "paper-trades", "--id", "exp-001", "--db", db_with_paper_trades],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 5
    assert data[0]["experiment_id"] == "exp-001"


def test_loop_state_query(db_with_paper_trades):
    # Add loop state
    db = Storage(db_with_paper_trades)
    db.save_loop_state(status="running", paper_trading_experiment="exp-001",
                       consecutive_rejections=2)
    db.close()

    result = subprocess.run(
        [sys.executable, "query.py", "loop-state", "--db", db_with_paper_trades],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "running"
    assert data["paper_trading_experiment"] == "exp-001"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_query.py::test_paper_trades_query tests/test_query.py::test_loop_state_query -v`
Expected: FAIL — subcommands don't exist

**Step 3: Add subcommands to query.py**

Add functions before `main()`:

```python
def cmd_paper_trades(db: Storage, args):
    rows = db.get_paper_trades(args.id)
    print(json.dumps(rows, indent=2, default=str))


def cmd_loop_state(db: Storage, args):
    state = db.get_loop_state()
    if state is None:
        print(json.dumps({"status": "no state recorded"}))
    else:
        print(json.dumps(state, indent=2, default=str))
```

Add subparsers in `main()`:

```python
    p_paper = sub.add_parser("paper-trades", help="Query paper trades for an experiment")
    p_paper.add_argument("--id", required=True, help="Experiment ID")

    p_loop = sub.add_parser("loop-state", help="Query research loop state")
```

Add to dispatch dict:

```python
    {"experiments": cmd_experiments, "experiment": cmd_experiment,
     "strategy": cmd_strategy, "scores": cmd_scores,
     "paper-trades": cmd_paper_trades, "loop-state": cmd_loop_state}[args.command](db, args)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_query.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add query.py tests/test_query.py
git commit -m "feat: query.py paper-trades + loop-state subcommands"
```

---

### Task 8: Update agent prompts for paper trading

**Files:**
- Modify: `.claude/agents/backtest-auditor.md`
- Modify: `.claude/agents/strategy-promoter.md`

**Step 1: Update backtest-auditor.md**

Add to the "Available Commands" section:

```markdown
### View paper trading progress
```bash
python query.py paper-trades --id exp-001
```

### Check loop state
```bash
python query.py loop-state
```
```

Add to the "6 Validation Gates" table, update paper trading row:

```markdown
| Paper trading | 10 days shadow portfolio: non-negative return AND <1% underperformance vs baseline |
```

Add section:

```markdown
## Paper Trading

After passing 5 backtest gates, experiments enter 10-day paper trading:
- Shadow portfolio tracks daily positions + returns for both baseline and experiment
- Primary gate: experiment return >= 0 AND doesn't underperform baseline by >1%
- Secondary (logged): beat baseline overall, directional consistency %
- Use `python query.py paper-trades --id exp-NNN` to monitor progress
- Use `python query.py loop-state` to see if an experiment is currently paper trading
```

**Step 2: Update strategy-promoter.md**

Add to "Available Commands":

```markdown
### Check paper trading progress
```bash
python query.py paper-trades --id exp-001
```

### Check loop state
```bash
python query.py loop-state
```
```

Update "Decision Framework" section, add:

```markdown
### Paper testing state
- All 5 backtest gates pass → experiment enters `paper_testing` (not immediately promoted)
- 10 trading days of shadow portfolio tracking
- Only one experiment can paper trade at a time
- If a second experiment passes while one is paper trading, it gets discarded

### After paper trading
- Primary gate passes → promoted (LLM writes narrative)
- Primary gate fails → rejected
- On promotion: in-flight experiments backtested against old baseline are invalidated
```

**Step 3: Commit**

```bash
git add .claude/agents/backtest-auditor.md .claude/agents/strategy-promoter.md
git commit -m "feat: update agent prompts for paper trading awareness"
```

---

### Task 9: Integration test

**Files:**
- Create: `tests/test_m5_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_m5_integration.py
"""Verify M5 paper trading + hardening components work together."""
import pytest
import json
import subprocess
import sys
import pandas as pd
from datetime import date, datetime
from unittest.mock import MagicMock
from src.data.db import Storage
from src.research.paper_trader import PaperTrader
from src.research.promoter import Promoter
from src.research.auditor import evaluate_gates
from src.research.results import BacktestResult, WindowResult


@pytest.fixture
def db(tmp_path):
    db = Storage(str(tmp_path / "test.duckdb"))
    yield db
    db.close()


def test_full_paper_trading_flow(db):
    """End-to-end: experiment passes backtest → paper_testing → evaluate → promote/reject."""
    # 1. Simulate backtest gates passing
    baseline = BacktestResult("0.1", [
        WindowResult(i, "", "", "", "", metrics={"sharpe": 0.8, "max_drawdown": 0.1, "monthly_turnover": 0.1})
        for i in range(4)
    ], {"sharpe": 0.8, "max_drawdown": 0.1, "monthly_turnover": 0.1})

    experiment = BacktestResult("0.1-exp", [
        WindowResult(i, "", "", "", "", metrics={"sharpe": 1.2, "max_drawdown": 0.08, "monthly_turnover": 0.09})
        for i in range(4)
    ], {"sharpe": 1.2, "max_drawdown": 0.08, "monthly_turnover": 0.09})

    verdict = evaluate_gates(baseline, experiment)
    assert verdict["overall"] == "pass"
    assert "paper_trading" not in [g["name"] for g in verdict["gates"]]

    # 2. Promoter returns paper_testing
    promoter = Promoter()
    decision = promoter.decide_backtest(verdict, "exp-001", {"weights": {"trend": 0.40}})
    assert decision["decision"] == "paper_testing"

    # 3. Simulate 10 days of paper trading
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-001",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={"AAPL": "buy"},
            experiment_positions={"AAPL": "buy", "MSFT": "buy"},
            baseline_return=0.005,
            experiment_return=0.007,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=0.007 * (i + 1),
        )

    # 4. Evaluate paper trading gate
    gate_result = PaperTrader.evaluate_gate("exp-001", db)
    assert gate_result["passed"] is True
    assert gate_result["days"] == 10

    # 5. Final promotion decision
    final = promoter.decide_paper(gate_result, "exp-001", {"weights": {"trend": 0.40}})
    assert final["decision"] == "promoted"


def test_paper_trading_rejection_flow(db):
    """Experiment passes backtest but fails paper trading → rejected."""
    promoter = Promoter()

    # Simulate 10 days where experiment loses money
    for i in range(10):
        db.store_paper_trade(
            experiment_id="exp-002",
            trade_date=date(2026, 3, i + 1),
            baseline_positions={}, experiment_positions={},
            baseline_return=0.005, experiment_return=-0.003,
            baseline_cumulative=0.005 * (i + 1),
            experiment_cumulative=-0.003 * (i + 1),
        )

    gate_result = PaperTrader.evaluate_gate("exp-002", db)
    assert gate_result["passed"] is False

    final = promoter.decide_paper(gate_result, "exp-002", {"thresholds": {"buy": 75}})
    assert final["decision"] == "rejected"


def test_loop_state_persistence(db):
    """Loop state survives DB close/reopen."""
    db.save_loop_state(
        status="running",
        paper_trading_experiment="exp-001",
        paper_start_date=date(2026, 3, 1),
        consecutive_rejections=5,
    )
    db_path = db.conn.execute("SELECT current_setting('database')").fetchone()[0]
    db.close()

    db2 = Storage(db_path)
    state = db2.get_loop_state()
    db2.close()
    assert state["status"] == "running"
    assert state["paper_trading_experiment"] == "exp-001"
    assert state["consecutive_rejections"] == 5


def test_invalidation_on_promotion(db):
    """In-flight experiments get invalidated when baseline changes."""
    db.store_experiment("exp-001", "0.1", {}, "promoted one")
    db.update_experiment_decision("exp-001", "promoted", {})
    db.store_experiment("exp-002", "0.1", {}, "in flight")
    # exp-002 has no decision (in-flight)
    db.store_experiment("exp-003", "0.1", {}, "paper testing")
    db.update_experiment_decision("exp-003", "paper_testing", {})

    db.invalidate_inflight_experiments(exclude_id="exp-003")

    assert db.get_experiment("exp-001")["decision"] == "promoted"
    assert db.get_experiment("exp-002")["decision"] == "invalidated"
    assert db.get_experiment("exp-003")["decision"] == "paper_testing"


def test_query_paper_trades_cli(db, tmp_path):
    """query.py paper-trades subcommand works."""
    db_path = str(tmp_path / "test2.duckdb")
    db2 = Storage(db_path)
    db2.store_paper_trade("exp-001", date(2026, 3, 1), {}, {}, 0.01, 0.02, 0.01, 0.02)
    db2.close()

    result = subprocess.run(
        [sys.executable, "query.py", "paper-trades", "--id", "exp-001", "--db", db_path],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
```

**Step 2: Run test**

Run: `pytest tests/test_m5_integration.py -v`
Expected: All pass

**Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_m5_integration.py
git commit -m "test: M5 integration tests — paper trading flow, state persistence, invalidation"
```

---

## Summary

| Task | What | Files |
|---|---|---|
| 1 | DB tables + methods | `src/data/db.py`, `tests/test_db_paper_trading.py` |
| 2 | PaperTrader shadow portfolio | `src/research/paper_trader.py`, `tests/test_paper_trader.py` |
| 3 | Promoter paper_testing state | `src/research/promoter.py`, `tests/test_promoter_paper.py` |
| 4 | Remove auditor paper stub | `src/research/auditor.py`, `tests/test_auditor_no_paper_stub.py` |
| 5 | Loop paper trading integration | `src/research/loop.py`, `tests/test_loop_paper_trading.py` |
| 6 | Graceful shutdown + logging | `research.py`, `tests/test_graceful_shutdown.py` |
| 7 | query.py paper-trades + loop-state | `query.py`, `tests/test_query.py` |
| 8 | Update agent prompts | `.claude/agents/backtest-auditor.md`, `.claude/agents/strategy-promoter.md` |
| 9 | Integration test | `tests/test_m5_integration.py` |

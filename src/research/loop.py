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

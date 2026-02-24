# src/research/loop.py
import time
import logging
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

logger = logging.getLogger(__name__)

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
        self.consecutive_rejections = 0

    def run(self, max_iterations: int | None = None) -> list[dict]:
        """Run the research loop. Returns list of iteration results."""
        results = []
        iteration = 0
        while True:
            if max_iterations and iteration >= max_iterations:
                break
            if self.consecutive_rejections >= self.max_consecutive_rejections:
                logger.info(f"Pausing: {self.consecutive_rejections} consecutive rejections")
                break

            result = self.run_one_iteration()
            results.append(result)

            if result["decision"] == "rejected":
                self.consecutive_rejections += 1
            else:
                self.consecutive_rejections = 0

            iteration += 1

            # Only sleep between iterations for open-ended runs
            if max_iterations is None:
                time.sleep(self.cooldown_seconds)

        self.db.close()
        return results

    def run_one_iteration(self) -> dict:
        # Load current baseline
        config_path = self.registry.get_current_config_path()
        baseline_config = load_strategy(config_path)

        # Backtest baseline
        baseline_bt = Backtester(baseline_config)
        baseline_result = baseline_bt.run(self.tickers, self.bars)

        # Build context
        baseline_snapshot = {
            "weights": baseline_config.weights,
            "thresholds": baseline_config.thresholds,
            "filters": baseline_config.filters,
        }
        recent = self.db.get_recent_experiments(limit=10)
        context = build_context_summary(
            baseline_result.aggregate_metrics, baseline_snapshot, recent
        )

        # Propose experiment
        proposal = self.proposer.propose(context)
        if proposal is None:
            return {"experiment_id": None, "decision": "skipped", "reason": "no valid proposal"}

        # Validate
        errors = validate_config_diff(baseline_snapshot, proposal["config_diff"])
        if errors:
            logger.warning(f"Invalid proposal: {errors}")
            return {"experiment_id": None, "decision": "skipped", "reason": f"invalid: {errors}"}

        # Create experiment
        exp = self.manager.create(
            parent_version=baseline_config.version,
            config_diff=proposal["config_diff"],
            hypothesis=proposal["hypothesis"],
        )

        # Build experiment config
        merged_dict = apply_diff(baseline_snapshot, proposal["config_diff"])
        exp_config = _build_config(baseline_config, merged_dict)

        # Backtest experiment
        exp_bt = Backtester(exp_config)
        exp_result = exp_bt.run(self.tickers, self.bars)

        # Evaluate gates
        verdict = evaluate_gates(baseline_result, exp_result)

        # Decide
        decision = self.promoter.decide(verdict, exp["experiment_id"], proposal["config_diff"])

        # Promote if needed
        if decision["decision"] == "promoted":
            new_version = self.registry.promote(
                parent_version=baseline_config.version,
                config_diff=proposal["config_diff"],
                metrics=exp_result.aggregate_metrics,
            )
            decision["new_version"] = new_version
            logger.info(f"Promoted {exp['experiment_id']} -> v{new_version}")

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

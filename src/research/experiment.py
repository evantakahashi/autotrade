# src/research/experiment.py
import json
import re
import yaml
from pathlib import Path
from src.data.db import Storage

class ExperimentManager:
    def __init__(self, db: Storage, experiments_dir: str = "experiments"):
        self.db = db
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(exist_ok=True)

    def create(self, parent_version: str, config_diff: dict, hypothesis: str) -> dict:
        exp_id = self._next_id()
        # Create slug from hypothesis (first few content words)
        words = re.sub(r"[^a-z0-9\s]+", "", hypothesis.lower().strip()).split()
        # Filter out short stopwords for a better slug
        content_words = [w for w in words if len(w) > 2 or w in ("buy", "sell")]
        slug = "-".join(content_words[:3])[:40].strip("-")
        dir_name = f"{exp_id}-{slug}"
        exp_dir = self.experiments_dir / dir_name
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Write config.yaml
        (exp_dir / "config.yaml").write_text(yaml.dump(config_diff, default_flow_style=False))

        # Write hypothesis.md
        (exp_dir / "hypothesis.md").write_text(f"# {exp_id}: {hypothesis}\n\n"
                                                 f"Parent version: {parent_version}\n\n"
                                                 f"Config diff:\n```yaml\n{yaml.dump(config_diff)}\n```\n")

        # Store in DB
        self.db.store_experiment(exp_id, parent_version, config_diff, hypothesis)

        return {
            "experiment_id": exp_id,
            "dir_name": dir_name,
            "parent_version": parent_version,
            "config_diff": config_diff,
            "hypothesis": hypothesis,
        }

    def record_decision(self, experiment_id: str, dir_name: str,
                        decision: str, metrics: dict, reasoning: str):
        # Update DB
        self.db.update_experiment_decision(experiment_id, decision, metrics)

        # Write decision.md
        exp_dir = self.experiments_dir / dir_name
        exp_dir.mkdir(exist_ok=True)
        (exp_dir / "decision.md").write_text(
            f"# Decision: {decision.upper()}\n\n"
            f"## Metrics\n```json\n{json.dumps(metrics, indent=2)}\n```\n\n"
            f"## Reasoning\n{reasoning}\n"
        )

        # Write results.json
        (exp_dir / "results.json").write_text(json.dumps({
            "experiment_id": experiment_id,
            "decision": decision,
            "metrics": metrics,
        }, indent=2))

    def _next_id(self) -> str:
        experiments = self.db.get_experiments()
        if not experiments:
            return "exp-001"
        ids = [e["experiment_id"] for e in experiments]
        nums = [int(re.search(r"\d+", eid).group()) for eid in ids if re.search(r"\d+", eid)]
        next_num = max(nums) + 1 if nums else 1
        return f"exp-{next_num:03d}"

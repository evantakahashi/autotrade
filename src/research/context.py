# src/research/context.py
import json

def build_context_summary(
    baseline_metrics: dict,
    baseline_config: dict,
    recent_experiments: list[dict],
    max_experiments: int = 10,
) -> str:
    """Build a structured context summary for the LLM proposer."""
    lines = []

    # Baseline performance
    lines.append("## Current Baseline Strategy")
    lines.append(f"- Sharpe: {baseline_metrics.get('sharpe', 'N/A')}")
    lines.append(f"- CAGR: {baseline_metrics.get('cagr', 'N/A')}")
    lines.append(f"- Max Drawdown: {baseline_metrics.get('max_drawdown', 'N/A')}")
    lines.append(f"- Hit Rate: {baseline_metrics.get('hit_rate', 'N/A')}")

    # Baseline config
    lines.append("\n## Baseline Config")
    weights = baseline_config.get("weights", {})
    if weights:
        lines.append("Weights: " + ", ".join(f"{k}={v}" for k, v in weights.items()))
    thresholds = baseline_config.get("thresholds", {})
    if thresholds:
        lines.append("Thresholds: " + ", ".join(f"{k}={v}" for k, v in thresholds.items()))
    filters = baseline_config.get("filters", {})
    if filters:
        lines.append("Filters: " + ", ".join(f"{k}={v}" for k, v in filters.items()))

    # Recent experiments
    experiments = recent_experiments[:max_experiments]
    if not experiments:
        lines.append("\n## Recent Experiments\nNo experiments run yet.")
    else:
        lines.append(f"\n## Recent Experiments ({len(experiments)} most recent)")
        rejected_changes = []
        promoted_changes = []
        for exp in experiments:
            eid = exp.get("experiment_id", "?")
            decision = exp.get("decision", "pending")
            diff_raw = exp.get("config_diff", "{}")
            diff = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
            metrics_raw = exp.get("metrics", "{}")
            metrics = json.loads(metrics_raw) if isinstance(metrics_raw, str) else (metrics_raw or {})
            sharpe = metrics.get("sharpe", "?")
            diff_summary = _summarize_diff(diff)
            line = f"- {eid}: {diff_summary} → {decision} (Sharpe: {sharpe})"
            lines.append(line)
            if decision == "rejected":
                rejected_changes.append(diff_summary)
            elif decision == "promoted":
                promoted_changes.append(diff_summary)

        # Synthesize patterns
        if rejected_changes:
            lines.append(f"\nRejected approaches: {'; '.join(rejected_changes[:5])}")
        if promoted_changes:
            lines.append(f"Successful approaches: {'; '.join(promoted_changes[:5])}")

    # Suggestions
    lines.append("\n## Unexplored Areas")
    explored_keys = set()
    for exp in experiments:
        diff_raw = exp.get("config_diff", "{}")
        diff = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
        for section in diff.values():
            if isinstance(section, dict):
                explored_keys.update(section.keys())
    all_keys = set(weights.keys()) | set(thresholds.keys()) | set(filters.keys())
    unexplored = all_keys - explored_keys
    if unexplored:
        lines.append(f"Not yet tested: {', '.join(sorted(unexplored))}")
    else:
        lines.append("All parameters have been tested at least once. Try combinations or larger changes.")

    return "\n".join(lines)

def _summarize_diff(diff: dict) -> str:
    parts = []
    for section, changes in diff.items():
        if isinstance(changes, dict):
            for k, v in changes.items():
                parts.append(f"{k}→{v}")
        else:
            parts.append(f"{section}→{changes}")
    return ", ".join(parts) if parts else "no changes"

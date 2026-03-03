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

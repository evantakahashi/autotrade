# src/research/promoter.py
import anthropic

DECISION_PROMPT = """You are a strategy promoter for a quant autoresearch system.

An experiment has passed ALL validation gates. Review the results and write a brief promotion rationale.

Experiment: {experiment_id}
Config changes: {config_diff}

Gate results:
{gate_details}

Write 2-3 sentences explaining why this change is being promoted. Be specific about the metrics."""

class Promoter:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def decide(self, verdict: dict, experiment_id: str, config_diff: dict) -> dict:
        # Auto-reject if any gate failed
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

        # All gates pass — call LLM for promotion narrative
        gate_details = "\n".join(
            f"  {g['name']}: PASS — {g['detail']}"
            for g in verdict["gates"]
        )
        prompt = DECISION_PROMPT.format(
            experiment_id=experiment_id,
            config_diff=config_diff,
            gate_details=gate_details,
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
            reasoning = f"All gates passed. Auto-promoting. (LLM unavailable: {e})"

        return {
            "decision": "promoted",
            "reasoning": reasoning,
        }

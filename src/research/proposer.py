# src/research/proposer.py
import json
import re
import anthropic

SYSTEM_PROMPT = """You are a quantitative signal researcher for a stock ranking system.

Your job: propose ONE small, testable change to the strategy config.

Rules:
- Propose exactly one change (a weight adjustment, threshold change, or filter modification)
- Changes must be small and incremental (e.g., shift a weight by 0.05, not 0.30)
- Weights must sum to 1.0 after your change
- Do NOT propose changes that were recently rejected (see experiment history)
- Explain your hypothesis in one sentence

You MUST respond with a JSON block in this exact format:
```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "One sentence explaining why this change should improve performance"
}
```

The config_diff should only include the keys you want to change. Unchanged values will be kept from baseline."""

class Proposer:
    def __init__(self, model: str = "claude-sonnet-4-20250514", max_retries: int = 3):
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_retries = max_retries

    def propose(self, context_summary: str) -> dict | None:
        for attempt in range(self.max_retries):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context_summary}],
            )
            text = response.content[0].text
            result = parse_proposal(text)
            if result is not None:
                return result
        return None

def parse_proposal(text: str) -> dict | None:
    """Extract JSON proposal from LLM response."""
    # Try to find ```json ... ``` block
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "config_diff" in data and "hypothesis" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    match = re.search(r"\{[^{}]*\"config_diff\"[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "config_diff" in data and "hypothesis" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None

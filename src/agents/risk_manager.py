# src/agents/risk_manager.py
from collections import Counter
from src.models.types import Recommendation

class RiskManager:
    def __init__(self, max_sector_pct: float = 0.40, stability_margin: float = 3.0):
        self.max_sector_pct = max_sector_pct
        self.stability_margin = stability_margin

    def review(self, recommendations: list[Recommendation],
               thresholds: dict | None = None) -> list[str]:
        warnings = []
        if not recommendations:
            return warnings

        # Sector concentration
        sectors = [r.signal_scores.get("sector", "Unknown") for r in recommendations
                   if r.action == "buy"]
        if sectors:
            counts = Counter(sectors)
            for sector, count in counts.items():
                pct = count / len(recommendations)
                if pct > self.max_sector_pct:
                    warnings.append(
                        f"Sector concentration: {count}/{len(recommendations)} "
                        f"recommendations in {sector} ({pct:.0%})"
                    )

        # Score stability: flag recommendations near threshold boundaries
        if thresholds:
            buy_thresh = thresholds.get("buy", 70)
            sell_thresh = thresholds.get("sell", 40)
            for r in recommendations:
                if r.action == "buy" and r.composite_score < buy_thresh + self.stability_margin:
                    warnings.append(
                        f"Borderline/unstable: {r.ticker} buy at {r.composite_score:.1f} "
                        f"(threshold {buy_thresh}, margin {self.stability_margin})"
                    )
                elif r.action == "sell" and r.composite_score > sell_thresh - self.stability_margin:
                    warnings.append(
                        f"Borderline/unstable: {r.ticker} sell at {r.composite_score:.1f} "
                        f"(threshold {sell_thresh}, margin {self.stability_margin})"
                    )

        # Total position size check
        buy_recs = [r for r in recommendations if r.action == "buy"]
        total_alloc = sum(r.risk_params.get("max_position_pct", 10) for r in buy_recs)
        if total_alloc > 100:
            warnings.append(
                f"Total allocation {total_alloc:.0f}% exceeds 100% — reduce position sizes"
            )

        return warnings

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, ArrowUpRight } from "lucide-react"

const stats = [
  { label: "Sharpe Ratio", value: "1.24", trend: "+0.08" },
  { label: "CAGR", value: "18.3%", trend: "+2.1%" },
  { label: "Max Drawdown", value: "12.1%", trend: "-1.2%" },
  { label: "Win Rate", value: "62%", trend: "+3%" },
]

export function CurrentStrategyCard() {
  return (
    <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="flex flex-row items-start justify-between border-b border-border/50 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
            <TrendingUp className="size-5" />
          </div>
          <div className="flex flex-col">
            <CardTitle className="text-base font-semibold tracking-tight">Current Strategy</CardTitle>
            <span className="text-xs text-muted-foreground">Promoted Mar 8, 2026</span>
          </div>
        </div>
        <Badge variant="secondary" className="rounded-lg border-0 bg-muted/80 font-mono text-xs">
          v0.2
        </Badge>
      </CardHeader>
      <CardContent className="pt-5">
        <div className="grid grid-cols-2 gap-5">
          {stats.map((stat) => (
            <div key={stat.label} className="group flex flex-col gap-2 rounded-xl bg-muted/30 p-4 ring-1 ring-border/50 transition-colors hover:bg-muted/50">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {stat.label}
              </span>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-2xl font-bold tabular-nums tracking-tight">
                  {stat.value}
                </span>
                <span className="flex items-center gap-0.5 text-xs font-medium text-success">
                  <ArrowUpRight className="size-3" />
                  {stat.trend}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

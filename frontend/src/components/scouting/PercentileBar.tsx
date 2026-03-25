import { cn } from "@/lib/utils";

interface PercentileBarProps {
  metric: string;
  value: number | null;
  percentile: number | null;
  compact?: boolean;
}

function getTierColor(p: number | null) {
  if (p == null) return "bg-muted";
  if (p < 33) return "bg-destructive";
  if (p < 66) return "bg-warning";
  return "bg-success";
}

export function PercentileBar({ metric, value, percentile, compact }: PercentileBarProps) {
  const isNull = percentile == null;

  return (
    <div className={cn("flex items-center gap-2", compact ? "text-xs" : "text-sm")}>
      <span className="w-36 truncate text-muted-foreground font-medium">{metric}</span>
      <span className="w-14 text-right tabular-nums text-foreground">
        {value != null ? value.toFixed(1) : "—"}
      </span>
      <div className="flex-1 h-4 bg-muted rounded-sm overflow-hidden relative min-w-[80px]">
        {isNull ? (
          <span className="absolute inset-0 flex items-center justify-center text-[10px] text-muted-foreground">
            N/A
          </span>
        ) : (
          <div
            className={cn("h-full rounded-sm transition-all", getTierColor(percentile))}
            style={{ width: `${percentile}%` }}
          />
        )}
      </div>
      <span className="w-8 text-right tabular-nums text-muted-foreground text-xs">
        {isNull ? "" : percentile}
      </span>
    </div>
  );
}

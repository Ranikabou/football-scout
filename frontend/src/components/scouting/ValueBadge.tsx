import { Badge } from "@/components/ui/badge";

interface ValueBadgeProps {
  valueRatio: number | null;
}

export function ValueBadge({ valueRatio }: ValueBadgeProps) {
  if (valueRatio == null) {
    return <Badge variant="outline" className="text-muted-foreground">No Valuation</Badge>;
  }
  if (valueRatio > 1.4) {
    return <Badge className="bg-success text-success-foreground">↑ Undervalued</Badge>;
  }
  if (valueRatio >= 0.8) {
    return <Badge variant="secondary">≈ Fair Value</Badge>;
  }
  return <Badge className="bg-destructive text-destructive-foreground">↓ Overvalued</Badge>;
}

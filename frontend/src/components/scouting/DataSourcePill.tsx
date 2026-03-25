import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const sourceColors: Record<string, string> = {
  StatsBomb: "bg-blue-600/20 text-blue-400 border-blue-600/30",
  Understat: "bg-purple-600/20 text-purple-400 border-purple-600/30",
  FBref: "bg-orange-600/20 text-orange-400 border-orange-600/30",
  Transfermarkt: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
};

export function DataSourcePill({ source }: { source: string }) {
  return (
    <Badge variant="outline" className={cn("text-[10px]", sourceColors[source] || "")}>
      {source}
    </Badge>
  );
}

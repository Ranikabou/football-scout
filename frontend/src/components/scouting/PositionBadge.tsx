import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const posColors: Record<string, string> = {
  GK: "bg-yellow-600/20 text-yellow-400 border-yellow-600/30",
  CB: "bg-red-600/20 text-red-400 border-red-600/30",
  FB: "bg-blue-600/20 text-blue-400 border-blue-600/30",
  CM: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
  WG: "bg-orange-600/20 text-orange-400 border-orange-600/30",
  ST: "bg-pink-600/20 text-pink-400 border-pink-600/30",
};

export function PositionBadge({ position }: { position: string }) {
  return (
    <Badge variant="outline" className={cn("text-xs font-semibold", posColors[position] || "")}>
      {position}
    </Badge>
  );
}

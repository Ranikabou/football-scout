import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function statusVariant(status: string) {
  switch (status.toLowerCase()) {
    case "active": return "default";
    case "degraded": return "secondary";
    case "unavailable": return "destructive";
    default: return "outline";
  }
}

export default function DataStatus() {
  const { data: sources, isLoading, error } = useQuery({
    queryKey: ["sources"],
    queryFn: api.getSources,
    retry: false,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Data Sources</h2>

      {error && (
        <div className="text-destructive text-sm p-3 bg-destructive/10 rounded-md">
          Failed to load data sources.
        </div>
      )}

      <Card>
        <CardContent className="pt-4">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : sources?.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Refresh</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((s) => (
                  <TableRow key={s.name}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(s.status) as any}>
                        {s.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {s.last_refresh ? new Date(s.last_refresh).toLocaleString() : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center py-8 text-muted-foreground text-sm">No data sources configured.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

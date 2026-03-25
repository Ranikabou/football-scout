import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatCurrency, formatRatio } from "@/lib/format";
import type { ShortlistQuery } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PositionBadge } from "@/components/scouting/PositionBadge";
import { ValueBadge } from "@/components/scouting/ValueBadge";
import { Badge } from "@/components/ui/badge";
import { Plus, X, Download, Play } from "lucide-react";
import { toast } from "@/hooks/use-toast";

const POS_GROUPS = ["GK", "CB", "FB", "CM", "WG", "ST"];

export default function ShortlistBuilder() {
  const navigate = useNavigate();
  const [posGroup, setPosGroup] = useState("CM");
  const [maxAge, setMaxAge] = useState(26);
  const [maxValue, setMaxValue] = useState<string>("");
  const [undervaluedOnly, setUndervaluedOnly] = useState(false);
  const [sortBy, setSortBy] = useState("value_ratio");
  const [thresholds, setThresholds] = useState<Array<{ metric: string; operator: string; value: number }>>([]);

  const { data: leagues } = useQuery({ queryKey: ["leagues"], queryFn: api.getLeagues, retry: false });

  const mutation = useMutation({
    mutationFn: (q: ShortlistQuery) => api.runShortlist(q),
    onError: (err) => {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    },
  });

  function addThreshold() {
    setThresholds([...thresholds, { metric: "", operator: ">=", value: 0 }]);
  }

  function removeThreshold(i: number) {
    setThresholds(thresholds.filter((_, idx) => idx !== i));
  }

  function runQuery() {
    const query: ShortlistQuery = {
      position_group: posGroup,
      max_age: maxAge,
      undervalued_only: undervaluedOnly,
      sort_by: sortBy,
      top_n: 50,
      metric_thresholds: thresholds.filter((t) => t.metric),
    };
    if (maxValue) query.max_market_value_eur = Number(maxValue);
    mutation.mutate(query);
  }

  function exportCSV() {
    if (!mutation.data?.players?.length) return;
    const rows = mutation.data.players;
    const headers = ["Name", "Team", "League", "Age", "Position", "Value", "Predicted", "Ratio"];
    const csv = [
      headers.join(","),
      ...rows.map((p) =>
        [p.player_name, p.team, p.league, p.age, p.position_group, p.market_value_eur ?? "", p.predicted_value_eur ?? "", p.value_ratio ?? ""].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "shortlist.csv";
    a.click();
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
      {/* Query Form */}
      <Card className="h-fit">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Query Builder</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-xs">Position Group</Label>
            <Select value={posGroup} onValueChange={setPosGroup}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {POS_GROUPS.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Max Age</Label>
            <Input type="number" value={maxAge} onChange={(e) => setMaxAge(Number(e.target.value))} />
          </div>
          <div>
            <Label className="text-xs">Max Market Value (€)</Label>
            <Input type="number" placeholder="No limit" value={maxValue} onChange={(e) => setMaxValue(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={undervaluedOnly} onCheckedChange={setUndervaluedOnly} />
            <Label className="text-xs">Undervalued only</Label>
          </div>
          <div>
            <Label className="text-xs">Sort By</Label>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="value_ratio">Value Ratio</SelectItem>
                <SelectItem value="similarity_score">Similarity</SelectItem>
                <SelectItem value="age">Age</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Metric Thresholds */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">Metric Filters</Label>
              <Button variant="ghost" size="sm" onClick={addThreshold}>
                <Plus className="h-3 w-3 mr-1" /> Add
              </Button>
            </div>
            {thresholds.map((t, i) => (
              <div key={i} className="flex gap-1 mb-1">
                <Input
                  placeholder="metric"
                  value={t.metric}
                  onChange={(e) => {
                    const copy = [...thresholds];
                    copy[i].metric = e.target.value;
                    setThresholds(copy);
                  }}
                  className="text-xs flex-1"
                />
                <Select
                  value={t.operator}
                  onValueChange={(v) => {
                    const copy = [...thresholds];
                    copy[i].operator = v;
                    setThresholds(copy);
                  }}
                >
                  <SelectTrigger className="w-16 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value=">=">≥</SelectItem>
                    <SelectItem value=">">{">"}</SelectItem>
                    <SelectItem value="<=">≤</SelectItem>
                    <SelectItem value="<">{"<"}</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  value={t.value}
                  onChange={(e) => {
                    const copy = [...thresholds];
                    copy[i].value = Number(e.target.value);
                    setThresholds(copy);
                  }}
                  className="w-16 text-xs"
                />
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => removeThreshold(i)}>
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>

          <Button onClick={runQuery} disabled={mutation.isPending} className="w-full">
            <Play className="mr-2 h-4 w-4" />
            {mutation.isPending ? "Running..." : "Run Query"}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm">
            Results
            {mutation.data && (
              <span className="font-normal text-muted-foreground ml-2">
                ({mutation.data.total_matches} matches)
              </span>
            )}
          </CardTitle>
          {mutation.data?.players?.length ? (
            <Button variant="outline" size="sm" onClick={exportCSV}>
              <Download className="mr-2 h-3 w-3" /> CSV
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          {mutation.isPending ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : mutation.data?.players?.length ? (
            <div className="rounded-md border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Player</TableHead>
                    <TableHead>Team</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead>Pos</TableHead>
                    <TableHead>League</TableHead>
                    <TableHead className="text-right">Value</TableHead>
                    <TableHead className="text-right">Ratio</TableHead>
                    <TableHead>Cluster</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mutation.data.players.map((p) => (
                    <TableRow
                      key={p.player_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/players/${p.player_id}`)}
                    >
                      <TableCell className="font-medium">{p.player_name}</TableCell>
                      <TableCell className="text-muted-foreground">{p.team}</TableCell>
                      <TableCell>{p.age}</TableCell>
                      <TableCell><PositionBadge position={p.position_group} /></TableCell>
                      <TableCell><Badge variant="outline" className="text-xs">{p.league}</Badge></TableCell>
                      <TableCell className="text-right tabular-nums">{formatCurrency(p.market_value_eur)}</TableCell>
                      <TableCell className="text-right">
                        <ValueBadge valueRatio={p.value_ratio} />
                      </TableCell>
                      <TableCell>
                        {p.cluster_label ? (
                          <Badge variant="secondary" className="text-xs">{p.cluster_label}</Badge>
                        ) : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-center py-12 text-muted-foreground text-sm">
              {mutation.data ? "No players match these filters. Try relaxing the age or value constraints." : "Configure filters and run a query."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

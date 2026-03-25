import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PositionBadge } from "@/components/scouting/PositionBadge";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Search } from "lucide-react";

export default function PlayerSearch() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const searchTerm = searchParams.get("search") || "";
  const league = searchParams.get("league") || "";
  const season = searchParams.get("season") || "";
  const position = searchParams.get("position") || "";
  const minMinutes = searchParams.get("min_minutes") || "";

  const { data: leagues } = useQuery({ queryKey: ["leagues"], queryFn: api.getLeagues, retry: false });
  const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: api.getSeasons, retry: false });
  const { data: positions } = useQuery({ queryKey: ["positions"], queryFn: api.getPositions, retry: false });

  const params: Record<string, string> = {};
  if (searchTerm) params.search = searchTerm;
  if (league) params.league = league;
  if (season) params.season = season;
  if (position) params.position = position;
  if (minMinutes) params.min_minutes = minMinutes;

  const { data, isLoading, error } = useQuery({
    queryKey: ["players", params],
    queryFn: () => api.searchPlayers(params),
    retry: false,
  });

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search players..."
            value={searchTerm}
            onChange={(e) => updateParam("search", e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={league} onValueChange={(v) => updateParam("league", v === "all" ? "" : v)}>
          <SelectTrigger className="w-36"><SelectValue placeholder="League" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Leagues</SelectItem>
            {leagues?.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={season} onValueChange={(v) => updateParam("season", v === "all" ? "" : v)}>
          <SelectTrigger className="w-32"><SelectValue placeholder="Season" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Seasons</SelectItem>
            {seasons?.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={position} onValueChange={(v) => updateParam("position", v === "all" ? "" : v)}>
          <SelectTrigger className="w-28"><SelectValue placeholder="Position" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {positions?.map((p) => <SelectItem key={p.group} value={p.group}>{p.group}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input
          type="number"
          placeholder="Min minutes"
          value={minMinutes}
          onChange={(e) => updateParam("min_minutes", e.target.value)}
          className="w-28"
        />
      </div>

      {error && (
        <div className="text-destructive text-sm p-3 bg-destructive/10 rounded-md">
          Failed to load players. Make sure the API is running.
        </div>
      )}

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player</TableHead>
              <TableHead>Team</TableHead>
              <TableHead>Age</TableHead>
              <TableHead>League</TableHead>
              <TableHead>Position</TableHead>
              <TableHead className="text-right">Minutes</TableHead>
              <TableHead className="text-right">Completeness</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : data?.players?.length ? (
              data.players.map((p) => (
                <TableRow
                  key={p.player_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/players/${p.player_id}`)}
                >
                  <TableCell className="font-medium">{p.player_name}</TableCell>
                  <TableCell className="text-muted-foreground">{p.team}</TableCell>
                  <TableCell>{p.age}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">{p.league}</Badge>
                  </TableCell>
                  <TableCell><PositionBadge position={p.position_group} /></TableCell>
                  <TableCell className="text-right tabular-nums">{p.minutes_played.toLocaleString()}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center gap-2 justify-end">
                      <Progress value={p.data_completeness_pct} className="w-16 h-2" />
                      <span className="text-xs text-muted-foreground tabular-nums w-8">
                        {p.data_completeness_pct}%
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                  {data ? "No players match these filters." : "Search for players to get started."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {data && (
        <p className="text-xs text-muted-foreground">
          Showing {data.players.length} of {data.total} results
        </p>
      )}
    </div>
  );
}

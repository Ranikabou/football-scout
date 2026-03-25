import type {
  PlayerSummary,
  PlayerDetail,
  SimilarPlayer,
  ClusterPoint,
  ScoutingReport,
  ShortlistQuery,
  PositionGroupInfo,
  DataSource,
} from "@/types/api";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${msg}`);
  }
  return res.json();
}

export const api = {
  // Players
  searchPlayers(params: Record<string, string>) {
    const qs = new URLSearchParams(params).toString();
    return apiFetch<{ players: PlayerSummary[]; total: number }>(`/api/players?${qs}`);
  },
  getPlayer(id: string) {
    return apiFetch<PlayerDetail>(`/api/players/${id}`);
  },
  getSimilarPlayers(id: string, n = 10) {
    return apiFetch<{ target: PlayerSummary; similar: SimilarPlayer[] }>(
      `/api/players/${id}/similar?n=${n}`
    );
  },

  // Shortlist
  runShortlist(query: ShortlistQuery) {
    return apiFetch<{ players: PlayerDetail[]; query: object; total_matches: number }>(
      "/api/shortlist",
      { method: "POST", body: JSON.stringify(query) }
    );
  },

  // Clusters
  getClusters(positionGroup: string) {
    return apiFetch<{ clusters: ClusterPoint[]; labels: string[] }>(
      `/api/clusters/${positionGroup}`
    );
  },

  // Reports
  getReport(playerId: string) {
    return apiFetch<ScoutingReport>(`/api/reports/${playerId}`);
  },

  // Meta
  getLeagues: () => apiFetch<string[]>("/api/meta/leagues"),
  getSeasons: () => apiFetch<string[]>("/api/meta/seasons"),
  getPositions: () => apiFetch<PositionGroupInfo[]>("/api/meta/positions"),
  getSources: () => apiFetch<DataSource[]>("/api/meta/sources"),
};

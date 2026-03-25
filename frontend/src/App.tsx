import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/components/scouting/Layout";
import PlayerSearch from "@/pages/PlayerSearch";
import PlayerDetail from "@/pages/PlayerDetail";
import ShortlistBuilder from "@/pages/ShortlistBuilder";
import ClusterExplorer from "@/pages/ClusterExplorer";
import DataStatus from "@/pages/DataStatus";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<PlayerSearch />} />
            <Route path="/players/:playerId" element={<PlayerDetail />} />
            <Route path="/shortlist" element={<ShortlistBuilder />} />
            <Route path="/clusters" element={<ClusterExplorer />} />
            <Route path="/status" element={<DataStatus />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

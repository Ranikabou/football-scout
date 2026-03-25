"""HDBSCAN archetype clustering with UMAP visualization."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Cluster label rules: map top z-scored metrics to descriptive names
CLUSTER_LABEL_RULES: dict[str, dict[tuple[str, ...], str]] = {
    "CM": {
        ("progressive_passes", "key_passes"): "Deep-Lying Playmaker",
        ("tackles_won", "pressures", "interceptions"): "Ball-Winning Midfielder",
        ("progressive_carries", "successful_dribbles"): "Box-to-Box Carrier",
        ("xag", "sca", "chance_creation"): "Advanced Playmaker",
    },
    "ST": {
        ("npxg", "shots", "goal_threat"): "Poacher",
        ("xag", "key_passes", "chance_creation"): "False 9 / Creator",
        ("aerials_won", "aerial_dominance"): "Target Man",
        ("pressures", "pressing_intensity"): "Press-Forward Striker",
    },
    "CB": {
        ("tackles_won", "interceptions", "blocks"): "Ball-Winning Defender",
        ("progressive_passes", "passes_completed"): "Ball-Playing Defender",
        ("aerials_won", "aerial_dominance"): "Aerial Dominant Defender",
        ("pressures", "pressing_intensity"): "Aggressive Presser",
    },
    "FB": {
        ("progressive_carries", "successful_dribbles"): "Attacking Fullback",
        ("tackles_won", "interceptions"): "Defensive Fullback",
        ("key_passes", "chance_creation"): "Creative Fullback",
        ("progressive_passes", "passes_completed"): "Inverted Fullback",
    },
    "WG": {
        ("goals", "npxg", "goal_threat"): "Goal-Scoring Winger",
        ("key_passes", "xag", "chance_creation"): "Creative Winger",
        ("progressive_carries", "successful_dribbles"): "Dribbling Winger",
        ("pressures", "pressing_intensity"): "Pressing Winger",
    },
    "GK": {
        ("passes_completed", "progressive_passes"): "Sweeper-Keeper",
    },
}

# Feature columns for clustering
CLUSTER_FEATURES = [
    "goals_p90", "npxg_p90", "xag_p90", "sca_p90",
    "progressive_passes_p90", "progressive_carries_p90",
    "key_passes_p90", "tackles_won_p90", "interceptions_p90",
    "blocks_p90", "pressures_p90", "pressure_success_pct",
    "successful_dribbles_p90", "aerial_dominance",
    "pressing_intensity", "chance_creation", "defensive_contrib",
    "progressive_action", "goal_threat",
]


class ArchetypeClusterer:
    """Cluster players into archetypes using HDBSCAN/KMeans + UMAP."""

    def cluster(
        self,
        feature_df: pd.DataFrame,
        position_group: str,
        output_dir: str | None = None,
    ) -> pd.DataFrame:
        """Cluster players and add labels + UMAP coordinates."""
        # Filter to position group
        if "position_group" in feature_df.columns:
            df = feature_df[feature_df["position_group"] == position_group].copy()
        else:
            df = feature_df.copy()

        if len(df) < 5:
            logger.warning(
                "Too few players (%d) for clustering position %s",
                len(df), position_group,
            )
            df["cluster_label"] = "Unknown"
            df["umap_x"] = np.nan
            df["umap_y"] = np.nan
            return df

        # Select available numeric features
        available = [f for f in CLUSTER_FEATURES if f in df.columns]

        # Drop columns with >50% missing
        keep = []
        for col in available:
            if df[col].notna().sum() / len(df) > 0.5:
                keep.append(col)
        available = keep

        if len(available) < 3:
            logger.warning("Too few features (%d) for clustering", len(available))
            df["cluster_label"] = "Unknown"
            df["umap_x"] = np.nan
            df["umap_y"] = np.nan
            return df

        # Impute remaining NaN with column median (for clustering only)
        X = df[available].copy()
        for col in available:
            median = X[col].median()
            X[col] = X[col].fillna(median)

        # StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Try HDBSCAN first
        labels = self._try_hdbscan(X_scaled)

        if labels is None:
            # Fall back to KMeans
            n_clusters = min(8, len(df) // 3)
            n_clusters = max(2, n_clusters)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            logger.info("Used KMeans with %d clusters", n_clusters)

        df = df.copy()
        df["cluster_id"] = labels

        # Label clusters via centroid profiling
        df["cluster_label"] = self._label_clusters(
            df, X_scaled, labels, available, position_group
        )

        # UMAP for visualization
        umap_coords = self._compute_umap(X_scaled)
        if umap_coords is not None:
            df["umap_x"] = umap_coords[:, 0]
            df["umap_y"] = umap_coords[:, 1]
        else:
            df["umap_x"] = np.nan
            df["umap_y"] = np.nan

        # Generate visualization if output_dir specified
        if output_dir and umap_coords is not None:
            self._save_visualization(df, position_group, output_dir)

        return df

    def _try_hdbscan(self, X_scaled: np.ndarray) -> np.ndarray | None:
        """Try HDBSCAN clustering; return None if too many noise points."""
        try:
            import hdbscan
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=10, min_samples=5
            )
            labels = clusterer.fit_predict(X_scaled)

            noise_pct = (labels == -1).sum() / len(labels)
            if noise_pct > 0.4:
                logger.info(
                    "HDBSCAN produced %.0f%% noise points, falling back to KMeans",
                    noise_pct * 100,
                )
                return None

            n_clusters = len(set(labels) - {-1})
            logger.info("HDBSCAN found %d clusters (%.0f%% noise)", n_clusters, noise_pct * 100)
            return labels
        except ImportError:
            logger.warning("hdbscan not installed, using KMeans")
            return None
        except Exception as e:
            logger.warning("HDBSCAN failed: %s, using KMeans", e)
            return None

    def _compute_umap(self, X_scaled: np.ndarray) -> np.ndarray | None:
        """Compute 2D UMAP embedding."""
        try:
            import umap
            reducer = umap.UMAP(n_components=2, random_state=42)
            return reducer.fit_transform(X_scaled)
        except ImportError:
            logger.warning("umap-learn not installed, skipping UMAP")
            return None
        except Exception as e:
            logger.warning("UMAP failed: %s", e)
            return None

    def _label_clusters(
        self,
        df: pd.DataFrame,
        X_scaled: np.ndarray,
        labels: np.ndarray,
        features: list[str],
        position_group: str,
    ) -> list[str]:
        """Assign descriptive labels to clusters based on centroid profiling."""
        rules = CLUSTER_LABEL_RULES.get(position_group, {})
        cluster_labels = []

        unique_clusters = sorted(set(labels))
        label_map: dict[int, str] = {}

        for cluster_id in unique_clusters:
            if cluster_id == -1:
                label_map[-1] = "Unclassified"
                continue

            mask = labels == cluster_id
            centroid = X_scaled[mask].mean(axis=0)

            # Find top-3 z-scored features
            top_indices = np.argsort(np.abs(centroid))[-3:][::-1]
            top_features = [features[i] for i in top_indices]

            # Match against rules
            best_label = None
            best_overlap = 0
            for rule_features, rule_label in rules.items():
                overlap = len(set(rule_features) & set(top_features))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_label = rule_label

            if best_label and best_overlap >= 1:
                label_map[cluster_id] = best_label
            else:
                # Fallback: describe by top feature
                label_map[cluster_id] = f"Cluster {cluster_id} ({top_features[0]})"

        return [label_map.get(l, "Unknown") for l in labels]

    def _save_visualization(
        self, df: pd.DataFrame, position_group: str, output_dir: str
    ) -> None:
        """Generate Plotly interactive scatter and save as HTML."""
        try:
            import plotly.express as px

            fig = px.scatter(
                df,
                x="umap_x", y="umap_y",
                color="cluster_label",
                hover_data=["player_name", "team", "league"],
                title=f"{position_group} Player Archetypes",
                labels={"umap_x": "UMAP 1", "umap_y": "UMAP 2"},
            )

            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            fig.write_html(str(out_path / f"clusters_{position_group}.html"))
            logger.info("Saved cluster viz to %s", out_path)
        except ImportError:
            logger.warning("plotly not installed, skipping visualization")
        except Exception as e:
            logger.warning("Failed to save visualization: %s", e)

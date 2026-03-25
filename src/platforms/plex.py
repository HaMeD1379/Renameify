"""
Plex Media Server platform configuration for Renameify.

Plex naming conventions:
- Movies: Movie Name (Year).ext
- TV Shows: Show Name (Year)/Season XX/Show Name - SXXEXX - Episode Title.ext

Plex Agents:
- Plex Movie: Uses Plex's own metadata
- Plex Series: Uses TheTVDB
- The Movie Database (TMDB): Popular alternative

Plex Scanners:
- Plex Movie: For movie libraries
- Plex TV Series: For TV show libraries
"""
from typing import Dict, Optional
from dataclasses import dataclass
from .base import Platform, NamingTemplate


# Plex Agents
PLEX_AGENTS = {
    "plex_movie": {
        "id": "com.plexapp.agents.imdb",
        "name": "Plex Movie",
        "description": "Plex's built-in movie agent using IMDB data",
    },
    "plex_series": {
        "id": "com.plexapp.agents.thetvdb",
        "name": "Plex Series",
        "description": "Plex's built-in TV series agent using TheTVDB",
    },
    "tmdb_movie": {
        "id": "tv.plex.agents.movie",
        "name": "The Movie Database",
        "description": "TMDB agent for movies (recommended)",
    },
    "tmdb_series": {
        "id": "tv.plex.agents.series",
        "name": "The Movie Database TV",
        "description": "TMDB agent for TV series (recommended)",
    },
    "hama": {
        "id": "com.plexapp.agents.hama",
        "name": "HamaTV",
        "description": "HTTP Anidb Metadata Agent for anime",
    },
}

# Plex Scanners
PLEX_SCANNERS = {
    "plex_movie": {
        "id": "Plex Movie",
        "name": "Plex Movie Scanner",
        "description": "Default scanner for movie libraries",
    },
    "plex_series": {
        "id": "Plex TV Series",
        "name": "Plex TV Series Scanner",
        "description": "Default scanner for TV libraries",
    },
    "plex_music": {
        "id": "Plex Music",
        "name": "Plex Music Scanner",
        "description": "Default scanner for music libraries",
    },
}


class PlexPlatform(Platform):
    """Plex Media Server platform configuration."""

    def __init__(self, agent: str = "tmdb_movie", scanner: str = "plex_movie"):
        self._agent = agent
        self._scanner = scanner

    @property
    def name(self) -> str:
        return "Plex"

    @property
    def id(self) -> str:
        return "plex"

    @property
    def agent(self) -> str:
        return self._agent

    @agent.setter
    def agent(self, value: str):
        if value in PLEX_AGENTS:
            self._agent = value

    @property
    def scanner(self) -> str:
        return self._scanner

    @scanner.setter
    def scanner(self, value: str):
        if value in PLEX_SCANNERS:
            self._scanner = value

    @property
    def templates(self) -> NamingTemplate:
        return NamingTemplate(
            movie_folder="{title} ({year})",
            movie_file="{title} ({year})",
            series_folder="{series} ({year_range})",
            season_folder="Season {season:02d}",
            episode_file="{series} - S{season:02d}E{episode:02d} - {episode_title}",
        )

    def format_movie_folder(self, title: str, year: Optional[int]) -> str:
        if year:
            return f"{title} ({year})"
        return title

    def format_movie_file(self, title: str, year: Optional[int]) -> str:
        if year:
            return f"{title} ({year})"
        return title

    def format_series_folder(self, series: str, year_range: str) -> str:
        if year_range:
            return f"{series} ({year_range})"
        return series

    def format_season_folder(self, season: int) -> str:
        return f"Season {season:02d}"

    def format_episode_file(
        self, series: str, season: int, episode: int, episode_title: Optional[str]
    ) -> str:
        if episode_title:
            return f"{series} - S{season:02d}E{episode:02d} - {episode_title}"
        return f"{series} - S{season:02d}E{episode:02d}"

    def get_options(self) -> Dict:
        return {
            "agents": PLEX_AGENTS,
            "scanners": PLEX_SCANNERS,
            "current_agent": self._agent,
            "current_scanner": self._scanner,
        }

    @staticmethod
    def get_agents() -> Dict:
        """Get available Plex agents."""
        return PLEX_AGENTS

    @staticmethod
    def get_scanners() -> Dict:
        """Get available Plex scanners."""
        return PLEX_SCANNERS


def get_plex_platform(agent: str = "tmdb_movie", scanner: str = "plex_movie") -> PlexPlatform:
    """Factory function to create a Plex platform instance."""
    return PlexPlatform(agent=agent, scanner=scanner)

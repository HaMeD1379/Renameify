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
from .base import Platform, NamingTemplate
from core.config import PLEX_AGENT_OPTIONS, PLEX_SCANNER_OPTIONS


PLEX_AGENTS = PLEX_AGENT_OPTIONS
PLEX_SCANNERS = PLEX_SCANNER_OPTIONS


class PlexPlatform(Platform):
    """Plex Media Server platform configuration."""

    def __init__(self, agent: str = "auto", scanner: str = "auto"):
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


def get_plex_platform(agent: str = "auto", scanner: str = "auto") -> PlexPlatform:
    """Factory function to create a Plex platform instance."""
    return PlexPlatform(agent=agent, scanner=scanner)

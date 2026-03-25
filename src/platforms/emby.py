"""
Emby Media Server platform configuration for Renameify.

Emby naming conventions are similar to Plex:
- Movies: Movie Name (Year).ext
- TV Shows: Show Name (Year)/Season XX/Show Name - SXXEXX - Episode Title.ext
"""
from typing import Dict, Optional
from .base import Platform, NamingTemplate


class EmbyPlatform(Platform):
    """Emby Media Server platform configuration."""

    @property
    def name(self) -> str:
        return "Emby"

    @property
    def id(self) -> str:
        return "emby"

    @property
    def templates(self) -> NamingTemplate:
        return NamingTemplate(
            movie_folder="{title} ({year})",
            movie_file="{title} ({year})",
            series_folder="{series} ({year_range})",
            season_folder="Season {season:02d}",
            episode_file="{series} S{season:02d}E{episode:02d} - {episode_title}",
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
            return f"{series} S{season:02d}E{episode:02d} - {episode_title}"
        return f"{series} S{season:02d}E{episode:02d}"


def get_emby_platform() -> EmbyPlatform:
    """Factory function to create an Emby platform instance."""
    return EmbyPlatform()

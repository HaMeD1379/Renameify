"""
Jellyfin Media Server platform configuration for Renameify.

Jellyfin naming conventions:
- Movies: Movie Name (Year).ext
- TV Shows: Show Name (Year)/Season XX/Show Name SXXEXX Episode Title.ext
"""
from typing import Dict, Optional
from .base import Platform, NamingTemplate


class JellyfinPlatform(Platform):
    """Jellyfin Media Server platform configuration."""

    @property
    def name(self) -> str:
        return "Jellyfin"

    @property
    def id(self) -> str:
        return "jellyfin"

    @property
    def templates(self) -> NamingTemplate:
        return NamingTemplate(
            movie_folder="{title} ({year})",
            movie_file="{title} ({year})",
            series_folder="{series} ({year_range})",
            season_folder="Season {season:02d}",
            episode_file="{series} S{season:02d}E{episode:02d} {episode_title}",
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
            return f"{series} S{season:02d}E{episode:02d} {episode_title}"
        return f"{series} S{season:02d}E{episode:02d}"


def get_jellyfin_platform() -> JellyfinPlatform:
    """Factory function to create a Jellyfin platform instance."""
    return JellyfinPlatform()

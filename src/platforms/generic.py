"""
Generic platform configuration for Renameify.

This platform uses square brackets instead of parentheses,
suitable for non-media server use cases.
"""
from typing import Dict, Optional
from .base import Platform, NamingTemplate


class GenericPlatform(Platform):
    """Generic platform with customizable naming."""

    def __init__(self):
        self._custom_templates = None

    @property
    def name(self) -> str:
        return "Generic"

    @property
    def id(self) -> str:
        return "generic"

    @property
    def templates(self) -> NamingTemplate:
        if self._custom_templates:
            return self._custom_templates
        return NamingTemplate(
            movie_folder="{title} [{year}]",
            movie_file="{title} [{year}]",
            series_folder="{series} [{year_range}]",
            season_folder="Season {season:02d}",
            episode_file="{series} S{season:02d}E{episode:02d} - {episode_title}",
        )

    def set_custom_templates(self, templates: NamingTemplate):
        """Set custom naming templates."""
        self._custom_templates = templates

    def format_movie_folder(self, title: str, year: Optional[int]) -> str:
        if year:
            return f"{title} [{year}]"
        return title

    def format_movie_file(self, title: str, year: Optional[int]) -> str:
        if year:
            return f"{title} [{year}]"
        return title

    def format_series_folder(self, series: str, year_range: str) -> str:
        if year_range:
            return f"{series} [{year_range}]"
        return series

    def format_season_folder(self, season: int) -> str:
        return f"Season {season:02d}"

    def format_episode_file(
        self, series: str, season: int, episode: int, episode_title: Optional[str]
    ) -> str:
        if episode_title:
            return f"{series} S{season:02d}E{episode:02d} - {episode_title}"
        return f"{series} S{season:02d}E{episode:02d}"


def get_generic_platform() -> GenericPlatform:
    """Factory function to create a Generic platform instance."""
    return GenericPlatform()

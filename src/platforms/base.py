"""
Platform base class and common functionality for Renameify.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class NamingTemplate:
    """Naming template for a platform."""
    movie_folder: str
    movie_file: str
    series_folder: str
    season_folder: str
    episode_file: str


class Platform(ABC):
    """Base class for media server platforms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform display name."""
        pass

    @property
    @abstractmethod
    def id(self) -> str:
        """Platform identifier."""
        pass

    @property
    @abstractmethod
    def templates(self) -> NamingTemplate:
        """Get naming templates for this platform."""
        pass

    @abstractmethod
    def format_movie_folder(self, title: str, year: Optional[int]) -> str:
        """Format a movie folder name."""
        pass

    @abstractmethod
    def format_movie_file(self, title: str, year: Optional[int]) -> str:
        """Format a movie file name."""
        pass

    @abstractmethod
    def format_series_folder(self, series: str, year_range: str) -> str:
        """Format a series folder name."""
        pass

    @abstractmethod
    def format_season_folder(self, season: int) -> str:
        """Format a season folder name."""
        pass

    @abstractmethod
    def format_episode_file(
        self, series: str, season: int, episode: int, episode_title: Optional[str]
    ) -> str:
        """Format an episode file name."""
        pass

    def get_options(self) -> Dict:
        """Get platform-specific options (override in subclasses)."""
        return {}

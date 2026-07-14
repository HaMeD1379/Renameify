import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.gpt_service import MediaInfo, identify_media_batch
from core.renamer import generate_rename_plan
from core.scanner import MediaFile


def media_file(path: Path) -> MediaFile:
    return MediaFile(
        path=path,
        filename=path.stem,
        extension=path.suffix,
        parent_folder=path.parent.name,
        size_mb=100.0,
    )


def plex_config() -> dict:
    return {
        "platform": "plex",
        "confidence_threshold": 80,
        "movie_file_template": "{title} ({year})",
        "movie_folder_template": "{title} ({year})",
        "series_folder_template": "{series} ({year_range})",
        "season_folder_template": "Season {season:02d}",
        "episode_file_template": "{series} - S{season:02d}E{episode:02d} - {episode_title}",
        "rename_subtitles": True,
    }


class SpecialsHotfixTests(unittest.TestCase):
    def test_misflagged_plex_movie_is_not_moved_to_specials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Movies"
            source = root / "Feature" / "messy.movie.mkv"
            source.parent.mkdir(parents=True)

            info = MediaInfo(
                original_filename=source.name,
                original_path=str(source),
                media_type="movie",
                title="The Matrix",
                year=1999,
                year_start=None,
                year_end=None,
                season=0,
                episode=1,
                episode_title="Special",
                confidence=95,
                notes=None,
                special_type="special",
            )

            plan = generate_rename_plan([media_file(source)], [info], str(root), plex_config())

            self.assertEqual(1, len(plan.high_confidence))
            self.assertEqual(
                source.parent / "The Matrix (1999).mkv",
                Path(plan.high_confidence[0]["new_path"]),
            )
            self.assertNotIn("Specials", Path(plan.high_confidence[0]["new_path"]).parts)

    def test_movie_under_specials_folder_is_normalized_as_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Movies" / "Specials" / "feature.mkv"
            source.parent.mkdir(parents=True)

            response = [{
                "original_filename": source.name,
                "media_type": "movie",
                "title": "The Menu",
                "year": 2022,
                "year_start": None,
                "year_end": None,
                "season": 0,
                "episode": 1,
                "episode_title": "Special",
                "special_type": "special",
                "confidence": 92,
                "notes": None,
            }]

            with patch("core.gpt_service.call_llm", return_value=json.dumps(response)):
                result = identify_media_batch([(source.name, str(source))], plex_config())

            self.assertEqual("movie", result[0].media_type)
            self.assertIsNone(result[0].season)
            self.assertIsNone(result[0].episode)
            self.assertIsNone(result[0].episode_title)
            self.assertIsNone(result[0].special_type)

    def test_valid_series_special_still_moves_to_show_specials_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "TV"
            source = root / "Example Show" / "Season 01" / "Specials" / "01.mkv"
            source.parent.mkdir(parents=True)

            info = MediaInfo(
                original_filename=source.name,
                original_path=str(source),
                media_type="series",
                title="Example Show",
                year=None,
                year_start=2020,
                year_end=None,
                season=0,
                episode=1,
                episode_title="Behind the Scenes",
                confidence=95,
                notes=None,
                special_type="behind_the_scenes",
            )

            plan = generate_rename_plan([media_file(source)], [info], str(root), plex_config())

            self.assertEqual(1, len(plan.high_confidence))
            self.assertEqual(
                root / "Example Show" / "Specials" / "Example Show - S00E01 - Behind the Scenes.mkv",
                Path(plan.high_confidence[0]["new_path"]),
            )

    def test_custom_prompt_does_not_persist_after_disabled(self):
        prompts = []

        def fake_call_llm(system_prompt, user_prompt, config, file_count=1, max_tokens=4096):
            prompts.append(system_prompt)
            filename = "custom.mkv" if len(prompts) == 1 else "default.mkv"
            return json.dumps([{
                "original_filename": filename,
                "media_type": "movie",
                "title": "Example",
                "year": 2020,
                "year_start": None,
                "year_end": None,
                "season": None,
                "episode": None,
                "episode_title": None,
                "special_type": None,
                "confidence": 90,
                "notes": None,
            }])

        with tempfile.TemporaryDirectory() as tmp:
            custom_path = Path(tmp) / "custom.mkv"
            default_path = Path(tmp) / "default.mkv"
            with patch("core.gpt_service.call_llm", side_effect=fake_call_llm):
                identify_media_batch(
                    [(custom_path.name, str(custom_path))],
                    plex_config(),
                    custom_prompt="CUSTOM PROMPT TOKEN",
                )
                identify_media_batch([(default_path.name, str(default_path))], plex_config())

        self.assertIn("CUSTOM PROMPT TOKEN", prompts[0])
        self.assertNotIn("CUSTOM PROMPT TOKEN", prompts[1])

    def test_selected_plex_movie_scanner_skips_series_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Movies" / "Show.S01E01.mkv"
            source.parent.mkdir(parents=True)
            config = {
                **plex_config(),
                "plex_options_enabled": True,
                "plex_scanner": "plex_movie",
                "plex_agent": "plex_movie",
            }
            response = [{
                "original_filename": source.name,
                "media_type": "series",
                "title": "Example Show",
                "year": None,
                "year_start": 2020,
                "year_end": None,
                "season": 1,
                "episode": 1,
                "episode_title": "Pilot",
                "special_type": None,
                "confidence": 92,
                "notes": None,
            }]

            with patch("core.gpt_service.call_llm", return_value=json.dumps(response)):
                result = identify_media_batch([(source.name, str(source))], config)

            self.assertEqual("unknown", result[0].media_type)
            self.assertIn("movie scanner", result[0].notes)

    def test_selected_plex_tv_scanner_skips_movie_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "TV" / "Movie.2020.mkv"
            source.parent.mkdir(parents=True)
            config = {
                **plex_config(),
                "plex_options_enabled": True,
                "plex_scanner": "plex_tv_series",
                "plex_agent": "plex_series",
            }
            response = [{
                "original_filename": source.name,
                "media_type": "movie",
                "title": "Example Movie",
                "year": 2020,
                "year_start": None,
                "year_end": None,
                "season": None,
                "episode": None,
                "episode_title": None,
                "special_type": None,
                "confidence": 92,
                "notes": None,
            }]

            with patch("core.gpt_service.call_llm", return_value=json.dumps(response)):
                result = identify_media_batch([(source.name, str(source))], config)

            self.assertEqual("unknown", result[0].media_type)
            self.assertIn("TV Series scanner", result[0].notes)


if __name__ == "__main__":
    unittest.main()

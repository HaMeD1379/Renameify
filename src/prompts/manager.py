"""
Prompt manager for Renameify.

Handles loading, saving, and managing prompts including custom user overrides.
"""
from typing import Optional, Dict
from pathlib import Path
import json

from .builtin import (
    MEDIA_SYSTEM_PROMPT,
    MEDIA_USER_PROMPT,
    MASS_RENAME_PROMPT,
    CUSTOM_PROMPT_TEMPLATE
)


class PromptManager:
    """Manages prompts for file renaming operations."""

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir
        self._custom_prompt: Optional[str] = None
        self._custom_prompt_enabled: bool = False

    def set_custom_prompt(self, prompt: str, enabled: bool = True):
        """Set a custom prompt override."""
        self._custom_prompt = prompt
        self._custom_prompt_enabled = enabled

    def get_custom_prompt(self) -> Optional[str]:
        """Get the custom prompt if enabled."""
        if self._custom_prompt_enabled and self._custom_prompt:
            return self._custom_prompt
        return None

    def clear_custom_prompt(self):
        """Clear the custom prompt."""
        self._custom_prompt = None
        self._custom_prompt_enabled = False

    def get_media_system_prompt(self) -> str:
        """Get the system prompt for media identification."""
        custom = self.get_custom_prompt()
        if custom:
            return f"Follow these custom instructions:\n\n{custom}\n\n" + MEDIA_SYSTEM_PROMPT
        return MEDIA_SYSTEM_PROMPT

    def get_media_user_prompt(self, filenames: str) -> str:
        """Get the user prompt for media identification."""
        return MEDIA_USER_PROMPT.format(filenames=filenames)

    def get_mass_rename_prompt(
        self,
        filenames: str,
        custom_instructions: str = ""
    ) -> str:
        """Get the prompt for mass/generic file renaming."""
        custom = self.get_custom_prompt()
        if custom:
            custom_instructions = f"{custom}\n\n{custom_instructions}" if custom_instructions else custom

        return MASS_RENAME_PROMPT.format(
            custom_instructions=custom_instructions,
            filenames=filenames
        )

    def get_custom_pattern_prompt(
        self,
        filenames: str,
        user_instructions: str
    ) -> str:
        """Get a prompt with user-defined custom instructions."""
        return CUSTOM_PROMPT_TEMPLATE.format(
            user_instructions=user_instructions,
            filenames=filenames
        )

    def save_prompt(self, name: str, prompt: str):
        """Save a custom prompt to file."""
        if not self._config_dir:
            return

        prompts_dir = self._config_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        prompt_file = prompts_dir / f"{name}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

    def load_prompt(self, name: str) -> Optional[str]:
        """Load a custom prompt from file."""
        if not self._config_dir:
            return None

        prompt_file = self._config_dir / "prompts" / f"{name}.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return None

    def list_saved_prompts(self) -> list:
        """List all saved custom prompts."""
        if not self._config_dir:
            return []

        prompts_dir = self._config_dir / "prompts"
        if not prompts_dir.exists():
            return []

        return [f.stem for f in prompts_dir.glob("*.txt")]

    def delete_prompt(self, name: str) -> bool:
        """Delete a saved custom prompt."""
        if not self._config_dir:
            return False

        prompt_file = self._config_dir / "prompts" / f"{name}.txt"
        if prompt_file.exists():
            prompt_file.unlink()
            return True
        return False


# Global prompt manager instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager(config_dir: Optional[Path] = None) -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None or config_dir is not None:
        _prompt_manager = PromptManager(config_dir)
    return _prompt_manager

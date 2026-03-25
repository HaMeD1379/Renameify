"""
Prompts module for Renameify.

Contains built-in prompts for media identification and
support for custom user-defined prompts.
"""
from .manager import PromptManager, get_prompt_manager
from .builtin import MEDIA_SYSTEM_PROMPT, MEDIA_USER_PROMPT, MASS_RENAME_PROMPT

from stgpytools import CustomIntEnum

__all__ = [
    'InstallModeEnum'
]


class InstallModeEnum(CustomIntEnum):
    """Enumeration for different installation modes of dependencies."""

    AUTO = 0
    """Automatically install missing dependencies without prompting."""

    PROMPT = 1
    """Prompt the user before installing missing dependencies."""

    MANUAL = 2
    """Do not install dependencies automatically; user must install manually."""

"""CLI commands for the application."""

from .developer import developer_group
from .development import development_group
from .migrate import makemigrations, migrate
from .seed import seed

__all__ = ("developer_group", "development_group", "makemigrations", "migrate", "seed")

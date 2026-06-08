"""Plugins."""

from litestar_granian import GranianPlugin
from litestar_saq import SAQPlugin

from .saq import saq_settings

granian = GranianPlugin()
saq = SAQPlugin(config=saq_settings)

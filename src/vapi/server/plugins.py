"""Plugins."""

from litestar_granian import GranianPlugin
from litestar_saq import SAQPlugin

from vapi.server.oauth import OAuth2ProviderPlugin

from .saq import saq_settings

granian = GranianPlugin()
oauth = OAuth2ProviderPlugin()
saq = SAQPlugin(config=saq_settings)

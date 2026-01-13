"""Plugins."""

from litestar_granian import GranianPlugin

from vapi.server.oauth import OAuth2ProviderPlugin

granian = GranianPlugin()
oauth = OAuth2ProviderPlugin()

"""Static files controller."""

import logging

from litestar.static_files import create_static_files_router

from vapi.constants import MODULE_ROOT_PATH

__all__ = ("html_static_files_router",)

HTML_DIR = MODULE_ROOT_PATH / "domain" / "assets" / "html"

logger = logging.getLogger("vapi")


html_static_files_router = create_static_files_router(
    path="/",
    directories=[HTML_DIR],
    html_mode=True,
    include_in_schema=False,
    opt={"exclude_from_auth": True},
)

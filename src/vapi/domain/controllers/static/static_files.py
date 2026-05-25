"""Static files controller."""

from pathlib import Path

from litestar import MediaType, Router, get
from litestar.response import Response
from litestar.static_files import create_static_files_router

__all__ = ("static_router",)

# Co-located with this controller: `content/` holds the payloads baked into the root routes
# below; `public/` is the file tree served verbatim under /static.
CONTENT_DIR = Path(__file__).parent / "content"
PUBLIC_DIR = Path(__file__).parent / "public"

# Read at import: these ship with the package and never change at runtime, so serving them
# from memory avoids a filesystem read on every request and sidesteps the File-response
# default of Content-Disposition: attachment (which would make browsers download index.html).
_INDEX_HTML = (CONTENT_DIR / "index.html").read_text(encoding="utf-8")
_ROBOTS_TXT = (CONTENT_DIR / "robots.txt").read_text(encoding="utf-8")


@get("/", include_in_schema=False, opt={"exclude_from_auth": True}, sync_to_thread=False)
def homepage() -> Response[str]:
    """Serve the branded landing page that points visitors to the documentation."""
    return Response(content=_INDEX_HTML, media_type=MediaType.HTML)


@get("/robots.txt", include_in_schema=False, opt={"exclude_from_auth": True}, sync_to_thread=False)
def robots_txt() -> Response[str]:
    """Serve the robots policy that disallows all crawlers."""
    return Response(content=_ROBOTS_TXT, media_type=MediaType.TEXT)


# Scope static asset serving to /static/ so unknown paths fall through to the standard JSON
# 404 instead of every junk path being treated as a static-file lookup.
_static_files_router = create_static_files_router(
    path="/static",
    directories=[PUBLIC_DIR],
    include_in_schema=False,
    opt={"exclude_from_auth": True},
)

static_router = Router(
    path="/",
    route_handlers=[homepage, robots_txt, _static_files_router],
)

"""Static files controller."""

from pathlib import Path

from litestar import MediaType, Router, get
from litestar.response import Redirect, Response
from litestar.static_files import create_static_files_router

from vapi.constants import DOCS_URL

__all__ = ("static_router",)

# Co-located with this controller: `content/` holds the payloads baked into the root routes
# below; `public/` is the file tree served verbatim under /static.
CONTENT_DIR = Path(__file__).parent / "content"
PUBLIC_DIR = Path(__file__).parent / "public"

# Read at import: robots.txt ships with the package and never changes at runtime, so serving
# it from memory avoids a filesystem read on every request.
_ROBOTS_TXT = (CONTENT_DIR / "robots.txt").read_text(encoding="utf-8")


@get("/", include_in_schema=False, opt={"exclude_from_auth": True}, sync_to_thread=False)
def homepage() -> Redirect:
    """Redirect visitors at the bare domain to the documentation site.

    Uses a temporary (302) redirect so `/` can be repurposed later without browsers having
    cached a permanent redirect.
    """
    return Redirect(DOCS_URL, status_code=302)


@get("/robots.txt", include_in_schema=False, opt={"exclude_from_auth": True}, sync_to_thread=False)
def robots_txt() -> Response[str]:
    """Serve the robots policy that disallows all crawlers."""
    return Response(content=_ROBOTS_TXT, media_type=MediaType.TEXT)


def create_public_files_router(directory: Path) -> Router:
    """Build the router that serves the files in `directory` verbatim under /static."""
    # Scope static asset serving to /static/ so unknown paths fall through to the standard JSON
    # 404 instead of every junk path being treated as a static-file lookup.
    return create_static_files_router(
        path="/static",
        directories=[directory],
        include_in_schema=False,
        opt={"exclude_from_auth": True},
    )


static_router = Router(
    path="/",
    route_handlers=[homepage, robots_txt, create_public_files_router(PUBLIC_DIR)],
)

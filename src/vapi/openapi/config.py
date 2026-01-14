"""OpenAPI configuration."""

from textwrap import dedent

from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import (
    JsonRenderPlugin,
    RapidocRenderPlugin,
    RedocRenderPlugin,
    ScalarRenderPlugin,
    StoplightRenderPlugin,
    SwaggerRenderPlugin,
    YamlRenderPlugin,
)
from litestar.openapi.spec import (
    Components,
    Contact,
    ExternalDocumentation,
    License,
    Link,
    OpenAPIHeader,
    SecurityScheme,
    Server,
)

from vapi import __version__
from vapi.config import settings
from vapi.constants import AUTH_HEADER_KEY

from .tags import APITags

# TODO: Update the description
API_DESCRIPTION = dedent("""\
        Welcome to the detailed API documentation for Valentina Noir where each endpoint is documented in detail.

        > [!IMPORTANT] **IMPORTANT:** Before you start developing, be sure to **[read the overview documentation](https://docs.valentina-noir.com)** to understand the core concepts and features of the API.
""")


def create_openapi_config() -> OpenAPIConfig:
    """Create OpenAPI configuration with all tags."""
    return OpenAPIConfig(
        title=settings.name,
        version=__version__,
        contact=Contact(
            name="support",
            url="https://github.com/natelandau/valentina-noir",
            email="support@valentina-noir.com",
        ),
        servers=[
            Server(url="https://api.valentina-noir.com", description="Production"),
            Server(url="http://127.0.0.1:8000", description="Local Development"),
        ],
        description=API_DESCRIPTION,
        license=License(
            name="MIT License",
            identifier="MIT",
            url="https://opensource.org/licenses/MIT",
        ),
        use_handler_docstrings=True,
        render_plugins=[
            ScalarRenderPlugin(),
            JsonRenderPlugin(),
            YamlRenderPlugin(),
            RapidocRenderPlugin(),
            RedocRenderPlugin(),
            StoplightRenderPlugin(),
            SwaggerRenderPlugin(),
        ],
        path="/docs",
        components=Components(
            headers={AUTH_HEADER_KEY: OpenAPIHeader(description="API Key for authentication")},
            security_schemes={
                "API Key": SecurityScheme(
                    security_scheme_in="header",
                    type="apiKey",
                    name=AUTH_HEADER_KEY,
                    description="API Key for authentication",
                    scheme="apiKey",
                )
            },
        ),
        external_docs=ExternalDocumentation(
            url="https://docs.valentina-noir.com",
            description="Documentation",
        ),
        tags=APITags.get_all_tags(),
    )

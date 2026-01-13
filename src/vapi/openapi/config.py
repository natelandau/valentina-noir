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
    License,
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
        # Valentina Noir

        A comprehensive API for managing World of Darkness games.

        ## Features

        - Support for v4 and v5 of the World of Darkness system
        - Full support for vampires, werewolves, hunters, and mortals. Basic support for mages.
        - Dicerolling and gameplay mechanics
        - Character auto-generation
        - Storyteller NPC and character creation
        - Campaign and story tracking
        - Configurable dictionary of game terms and concepts
        - Multi-tenant support
        - Statistics and analytics
        - Settings to configure gameplay and rulesets

        ## System
        Valentina Noir is based on a customized version of the World of Darkness system. The major differences are:

        ### Dice Rolling
        Dice are rolled as a single pool of D10s with a set difficulty. The number of success determines the outcome of the roll.

        - `< 0` successes: Botch
        - `0` successes: Failure
        - `> 0` successes: Success
        - `> dice pool` successes: Critical success

        - Rolled ones count as `-1` success
        - Rolled tens count as `2` successes
        - Rolled ones and tens cancel each other out

        ### Cool Points
        Cool points can be awarded by the Storyteller as a reward to players. Each cool point is worth `10xp`.

        ### Character Creation

        - Character's can have specific `concepts` that come with specialties and favored abilities.
        - Randomly generated characters can be created in batches with xp spent to select one of the generated characters for the player.

        ### Gameplay Mechanics omitted on purpose
        - Blood pool and hunger
        - Rouse checks
        - Health level management


        ## Roadmap
        The following features are planned for the future:

        - Loresheets
        - Full mage support


        ## Getting Started

        1. [Create an account](https://valentina.dev/signup)
        2. [Generate API credentials](https://valentina.dev/settings/api)
        3. Authenticate using the `/oauth/token` endpoint
        4. Start making requests!

        ## Support

        - 📧 Email: support@valentina-noir.com
        - 💬 Discord: [Join our community](https://discord.gg/valentina-noir)
        - 📖 Docs: https://docs.valentina-noir.com
""")


def create_openapi_config() -> OpenAPIConfig:
    """Create OpenAPI configuration with all tags."""
    return OpenAPIConfig(
        title=settings.name,
        version=__version__,
        contact=Contact(
            name="natelandau",
            url="https://github.com/natelandau",
            email="valentinaapi@natelandau.com",
        ),
        # TODO: Add production and staging server URLs
        servers=[
            # Server(url="https://api.valentina.dev", description="Production"),  # noqa: ERA001
            # Server(url="https://staging-api.valentina.dev", description="Staging"),  # noqa: ERA001
            Server(url="http://127.0.0.1:8000", description="Local Development"),
        ],
        description=API_DESCRIPTION,
        license=License(
            name="Apache License 2.0",
            identifier="Apache-2.0",
            url="http://www.apache.org/licenses/LICENSE-2.0",
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
        tags=APITags.get_all_tags(),
    )

"""OpenAPI tags."""

from dataclasses import dataclass

from litestar.openapi.spec import Tag


@dataclass(frozen=True)
class TagMetadata:
    """Metadata for an OpenAPI tag."""

    name: str
    description: str
    external_docs_url: str | None = None

    def to_tag(self) -> Tag:
        """Convert to Litestar Tag object."""
        if self.external_docs_url:
            description = f"{self.description}\n\n📖 [Documentation]({self.external_docs_url})"
        else:
            description = self.description

        return Tag(
            name=self.name,
            description=description,
        )


class APITags:
    """Centralized registry of all API tags.

    Use these constants in controllers to ensure consistency
    with OpenAPI documentation.
    """

    CAMPAIGNS = TagMetadata(name="Campaigns", description="Game campaigns and story arcs")
    CAMPAIGNS_NOTES = TagMetadata(name="Campaigns - Notes", description="Campaign notes")
    CAMPAIGNS_ASSETS = TagMetadata(name="Campaigns - Assets", description="Campaign assets")
    CAMPAIGN_BOOKS = TagMetadata(
        name="Campaigns - Books",
        description="Campaign sourcebooks and rulebooks for World of Darkness games.",
    )
    CAMPAIGN_BOOK_NOTES = TagMetadata(
        name="Campaigns - Books - Notes",
        description="Notes attached to campaign books",
    )
    CAMPAIGN_BOOK_ASSETS = TagMetadata(
        name="Campaigns - Books - Assets", description="Campaign book assets"
    )
    CAMPAIGN_CHAPTERS = TagMetadata(
        name="Campaigns - Chapters", description="Chapters and sections within campaign books"
    )
    CAMPAIGN_CHAPTER_NOTES = TagMetadata(
        name="Campaigns - Chapters - Notes",
        description="Notes attached to campaign chapters",
    )
    CAMPAIGN_CHAPTER_ASSETS = TagMetadata(
        name="Campaigns - Chapters - Assets", description="Campaign chapter assets"
    )

    CHARACTERS = TagMetadata(name="Characters", description="Player and NPC character management")
    CHARACTERS_AUTOGEN = TagMetadata(
        name="Characters - Autogeneration",
        description="Automated character creation and generation",
    )
    CHARACTERS_BLUEPRINTS = TagMetadata(
        name="Characters - Blueprints", description="Character templates and blueprints"
    )
    CHARACTERS_INVENTORY = TagMetadata(
        name="Characters - Inventory", description="Character inventory and equipment management"
    )
    CHARACTERS_NOTES = TagMetadata(
        name="Characters - Notes", description="Character notes and story information"
    )
    CHARACTERS_SPECIAL_TRAITS = TagMetadata(
        name="Characters - Special Traits",
        description="Merits, flaws, and special character attributes",
    )
    CHARACTERS_TRAITS = TagMetadata(
        name="Characters - Traits",
        description="Character traits including attributes, abilities, and disciplines",
    )
    CHARACTERS_ASSETS = TagMetadata(name="Characters - Assets", description="Character assets")

    COMPANIES = TagMetadata(name="Companies", description="Multi-tenant company management")

    DEVELOPERS = TagMetadata(name="Developers", description="Developer tools and utilities")

    DICTIONARY_TERMS = TagMetadata(
        name="Dictionary Terms", description="Game terminology and glossary"
    )

    EXPERIENCE = TagMetadata(
        name="Experience", description="Experience points and character advancement"
    )

    GAMEPLAY = TagMetadata(name="Gameplay", description="Dice rolling and game mechanics")

    GLOBAL_ADMIN = TagMetadata(
        name="Global Admin", description="System-wide administration endpoints"
    )

    OAUTH = TagMetadata(name="OAuth", description="Authentication and authorization")

    OPTIONS = TagMetadata(name="Options", description="Configuration options and settings")

    STATISTICS = TagMetadata(name="Statistics", description="Game statistics and analytics")

    SYSTEM = TagMetadata(name="System", description="System health and information")

    USERS = TagMetadata(name="Users", description="User account management")
    USERS_NOTES = TagMetadata(name="Users - Notes", description="User notes")
    USERS_ASSETS = TagMetadata(name="Users - Assets", description="User assets")
    USERS_QUICKROLLS = TagMetadata(name="Users - Quickrolls", description="User quickrolls")

    @classmethod
    def get_all_tags(cls) -> list[Tag]:
        """Get all tags sorted alphabetically."""
        tags = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, TagMetadata):
                tags.append(attr)

        # Sort by tag name
        tags.sort(key=lambda t: t.name)
        return [t.to_tag() for t in tags]

    @classmethod
    def get_tag_names(cls) -> list[str]:
        """Get all tag names for validation."""
        return [t.name for t in cls.get_all_tags()]

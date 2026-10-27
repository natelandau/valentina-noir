"""Reference-data seed record."""

from tortoise import fields

from vapi.db.sql_models.base import BaseModel

__all__ = ("ReferenceDataSeed",)


class ReferenceDataSeed(BaseModel):
    """The fingerprint of the fixtures and migrations the last successful seed ran against.

    Holds at most one row. Startup compares it with the running build to detect reference
    data that was never re-seeded after a migration or fixture change.
    """

    fingerprint = fields.CharField(max_length=64)

    class Meta:
        """Tortoise ORM meta options."""

        table = "reference_data_seed"
        table_description = "Fingerprint of the build the reference data was last seeded from."

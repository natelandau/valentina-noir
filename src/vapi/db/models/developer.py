"""Developer model."""

from datetime import datetime
from typing import ClassVar

from beanie import (
    Insert,
    PydanticObjectId,
    Replace,
    Save,
    SaveChanges,
    Update,
    before_event,
)
from pydantic import BaseModel, EmailStr, Field

from vapi.constants import CompanyPermission
from vapi.lib.crypt import CryptService, hmac_sha256_hex
from vapi.utils.authentication import generate_api_key
from vapi.utils.strings import slugify
from vapi.utils.time import time_now

from .base import BaseDocument

_crypt_service = CryptService()


class CompanyPermissions(BaseModel):
    """Company permissions."""

    company_id: PydanticObjectId
    name: str | None = None
    permission: CompanyPermission


class Developer(BaseDocument):
    """Developer model."""

    username: str
    email: EmailStr
    api_key_fingerprint: str | None = None
    hashed_api_key: str | None = None
    key_generated: datetime = Field(default_factory=time_now)
    is_global_admin: bool = False
    companies: list[CompanyPermissions] = Field(default_factory=list)

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def slugify_username(self) -> None:
        """Get the slug for the user."""
        self.username = slugify(self.username)

    async def verify_api_key(self, api_key: str) -> bool:
        """Verify the API key."""
        return await _crypt_service.verify(api_key, self.hashed_api_key)

    async def generate_api_key(self) -> str:
        """Generate a new API key."""
        api_key = generate_api_key()
        self.hashed_api_key = await _crypt_service.hash(api_key)
        self.api_key_fingerprint = hmac_sha256_hex(data=api_key)
        self.key_generated = time_now()
        await self.save()

        return api_key

    class Settings:
        """Settings for the User model."""

        indexes: ClassVar[list[str]] = ["username", "email", "api_key_fingerprint"]

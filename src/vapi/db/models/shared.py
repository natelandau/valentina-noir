"""Shared models."""

from pydantic import BaseModel

from vapi.constants import SpecialtyType


class Specialty(BaseModel):
    """Special ability model."""

    name: str
    type: SpecialtyType
    description: str

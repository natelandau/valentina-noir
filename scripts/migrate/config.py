"""Configuration for the migration script."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OldDatabaseSettings(BaseSettings):
    """Settings for the old Valentina database."""

    model_config = SettingsConfigDict(
        env_prefix="OLD_",
        env_file="scripts/migrate/.env.old",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongo_uri: str = Field(description="MongoDB URI for the old database")
    mongo_database_name: str = Field(description="MongoDB database name for the old database")
    aws_access_key_id: str = Field(description="AWS access key ID for the old S3 bucket")
    aws_secret_access_key: str = Field(description="AWS secret access key for the old S3 bucket")
    s3_bucket_name: str = Field(description="S3 bucket name for the old database")


old_settings = OldDatabaseSettings()  # type: ignore[call-arg]

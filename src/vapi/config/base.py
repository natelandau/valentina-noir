"""API application settings."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

from vapi.constants import AUTH_HEADER_KEY, ENVAR_PREFIX, MODULE_ROOT_PATH, LogLevel
from vapi.utils.strings import slugify


def get_secret(filename: str) -> str:
    """Get a secret from the secrets directory."""
    path = Path(f"secrets/{filename}").resolve()

    if not path.exists():
        msg = f"Secret file not found at path: {str(path)!r}"
        raise ValueError(msg)

    return path.read_text("utf-8").strip()


# Credit: https://github.com/Rapptz/discord.py/blob/master/discord/utils.py
def is_docker() -> bool:
    """Check if the current process is running in a Docker container."""
    cgroup_path = Path("/proc/self/cgroup")
    dockerenv_path = Path("/.dockerenv")
    return dockerenv_path.exists() or (
        cgroup_path.is_file() and any("docker" in line for line in cgroup_path.open())
    )


class SAQSettings(BaseModel):
    """SAQ settings."""

    use_server_lifespan: bool = Field(default=True)
    web_enabled: bool = Field(default=False)
    processes: int = Field(default=1)
    enabled: bool = Field(default=True)
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="admin")


class AWSSettings(BaseModel):
    """AWS settings."""

    access_key_id: str | None = Field(default=None)
    secret_access_key: str | None = Field(default=None)
    s3_bucket_name: str | None = Field(default=None)
    cloudfront_origin_path: str | None = Field(default=None)
    cloudfront_url: str | None = Field(default=None)


class Server(BaseModel):
    """Server settings."""

    host: str = Field(default_factory=lambda: "0.0.0.0" if is_docker() else "127.0.0.1")  # noqa: S104
    port: int | None = None
    scheme: str = Field(default="https")
    keep_alive: int = Field(default=65)  # 65 seconds > AWS timeout
    reload: bool = Field(default=False)
    reload_dirs: list[str] = Field(default_factory=lambda: [str(MODULE_ROOT_PATH)])

    @computed_field  # type: ignore [prop-decorator]
    @property
    def url(self) -> str:
        """Get the FQDN for the server."""
        port = f":{self.port}" if self.port and self.port not in [80, 443] else ""
        return f"{self.scheme}://{self.host}{port}"


class RedisSettings(BaseModel):
    """Redis settings."""

    url: str = Field(default="redis://localhost:6379/0")
    timeout: int = Field(default=5)
    health_check_interval: int = Field(default=5)
    keepalive: bool = Field(default=True)

    # @computed_field  # type: ignore [prop-decorator]
    @property
    def client(self) -> Redis:
        """Get the Redis client."""
        return self.get_client()

    def get_client(self) -> Redis:
        """Get the Redis client."""
        return Redis.from_url(
            url=self.url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=self.timeout,
            socket_keepalive=self.keepalive,
            health_check_interval=self.health_check_interval,
        )


class MongoDBSettings(BaseModel):
    """MongoDB settings."""

    uri: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="valentina-noir")


class StoresSettings(BaseModel):
    """Settings for redis stores."""

    ttl: int = Field(default=60)
    authentication_cache_key: str = Field(default="auth_cache")
    response_cache_key: str = Field(default="response_cache")
    guard_session_key: str = Field(default="guard_session")
    rate_limit_key: str = Field(default="rate_limit")
    user_role_key: str = Field(default="user_role")
    idempotency_key: str = Field(default="idempotency")


class RateLimitPolicy(BaseModel):
    """Rate limit policy."""

    name: str
    capacity: int = Field(default=50)
    refill_rate: float
    priority: int = Field(default=0)
    set_headers: bool = Field(default=True)
    set_429_headers: bool = Field(default=True)


class RateLimitSettings(BaseModel):
    """Rate limit settings."""

    encryption_key: str | None = Field(default=None)
    policies: dict[str, RateLimitPolicy] = Field(default_factory=dict)


class OAuthSettings(BaseModel):
    """OAuth settings."""

    discord_client_id: str | None = Field(default=None)
    discord_client_secret: str | None = Field(default=None)
    discord_callback_url: str | None = Field(default=None)


class CORSSettings(BaseModel):
    """CORS settings."""

    enabled: bool = Field(default=False)
    allowed_origins: list[str] = Field(default=["*"])
    allow_origin_regex: str | None = Field(default=None)


class LoggingSettings(BaseModel):
    """Logging settings."""

    level: LogLevel = Field(default=LogLevel.INFO)
    file_path: Path | None = Field(default=None)
    time_in_console: bool = Field(default=True)
    saq_level: LogLevel = Field(default=LogLevel.INFO)
    asgi_server_level: LogLevel = Field(default=LogLevel.INFO)
    root_level: LogLevel = Field(default=LogLevel.INFO)
    request_log_fields: list[str] = Field(
        default_factory=lambda: ["path", "method", "query", "path_params", "body", "client"]
    )
    response_log_fields: list[str] = Field(default_factory=lambda: ["status_code"])
    obfuscate_headers: set[str] = Field(
        default_factory=lambda: {"Authorization", AUTH_HEADER_KEY, "X-CSRF-TOKEN"}
    )
    obfuscate_cookies: set[str] = Field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    log_exceptions: Literal["always", "debug", "never"] = Field(default="debug")


class Settings(BaseSettings):
    """API application settings."""

    model_config = SettingsConfigDict(
        env_prefix=ENVAR_PREFIX,
        extra="ignore",
        case_sensitive=False,
        env_file=[".env", ".env.secret"],
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    name: str
    debug: bool = Field(default=False)

    authentication_encryption_key: str

    docker_bootstrap: bool = Field(default=False)

    log: LoggingSettings = LoggingSettings()
    cors: CORSSettings = CORSSettings()
    mongo: MongoDBSettings = MongoDBSettings()
    oauth: OAuthSettings = OAuthSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    redis: RedisSettings = RedisSettings()
    server: Server = Server()
    stores: StoresSettings = StoresSettings()
    aws: AWSSettings = AWSSettings()
    saq: SAQSettings = SAQSettings()

    @computed_field  # type: ignore [prop-decorator]
    @property
    def slug(self) -> str:
        """Get the slug for the application."""
        return slugify(self.name)


settings = Settings()  # type: ignore [call-arg]

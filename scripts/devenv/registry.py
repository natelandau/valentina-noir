"""Machine-wide registry of isolated dev stacks, shared by every checkout."""

import fcntl
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

from scripts.devenv.files import write_private
from scripts.devenv.ports import StackPorts

SCHEMA_VERSION = 1
DESCRIPTION = (
    "Local Valentina Noir dev stacks on this machine. Each entry is one checkout with its own "
    "Docker Compose project, ports, and connection sheet."
)
MAIN_KEY = "main"
DEFAULT_REGISTRY_PATH = Path.home() / ".local" / "state" / "valentina-noir" / "environments.json"
REGISTRY_ENV_VAR = "VAPI_DEV_REGISTRY"


class RegistryFormatError(ValueError):
    """Raised when the registry file is not in a supported format."""


class SlotConflictError(RuntimeError):
    """Raised when a key is already claimed by a different, still existing checkout."""


def registry_path() -> Path:
    """Return the registry file path, honoring `VAPI_DEV_REGISTRY` when set.

    Resolved on every call so tests and other checkouts can redirect the registry.
    """
    override = os.environ.get(REGISTRY_ENV_VAR)
    return Path(override) if override else DEFAULT_REGISTRY_PATH


@dataclass
class Environment:
    """One checkout's stack as recorded in the registry."""

    key: str
    checkout: Path
    branch: str
    slot: int
    project: str
    ports: StackPorts
    api_url: str
    api_url_from_containers: str
    healthz_url: str
    connection_sheet: Path
    keys_file: Path
    developers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible values."""
        data = asdict(self)
        data["checkout"] = str(self.checkout)
        data["connection_sheet"] = str(self.connection_sheet)
        data["keys_file"] = str(self.keys_file)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Rebuild an environment from `to_dict` output."""
        return cls(
            key=data["key"],
            checkout=Path(data["checkout"]),
            branch=data["branch"],
            slot=data["slot"],
            project=data["project"],
            ports=StackPorts(**data["ports"]),
            api_url=data["api_url"],
            api_url_from_containers=data["api_url_from_containers"],
            healthz_url=data["healthz_url"],
            connection_sheet=Path(data["connection_sheet"]),
            # Entries written before the field existed sit in the same checkout layout
            keys_file=Path(
                data.get("keys_file") or Path(data["checkout"]) / ".dev" / "api-keys.json"
            ),
            developers=data.get("developers", []),
        )


class Registry:
    """The set of registered environments and slot claims, keyed by `Environment.key`."""

    def __init__(
        self,
        path: Path,
        environments: dict[str, Environment] | None = None,
        claims: dict[str, tuple[int, Path]] | None = None,
    ) -> None:
        self.path = path
        self._environments = environments or {}
        self._claims = claims or {}

    @classmethod
    def load(cls, path: Path | None = None) -> Self:
        """Read the registry, returning an empty one when the file does not exist.

        Raises:
            RegistryFormatError: If the file is not JSON, `schema_version` is missing or
                unsupported, or an entry lacks a required field.
        """
        path = path or registry_path()
        if not path.exists():
            return cls(path)
        try:
            raw = json.loads(path.read_text())
            version = raw.get("schema_version")
            if version != SCHEMA_VERSION:
                msg = f"{path}: expected schema_version {SCHEMA_VERSION}, found {version!r}"
                raise RegistryFormatError(msg)
            environments = {
                key: Environment.from_dict(value) for key, value in raw["environments"].items()
            }
            claims = {
                key: (value["slot"], Path(value["checkout"]))
                for key, value in raw.get("slots", {}).items()
            }
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
            msg = f"{path} is not a valid dev stack registry ({type(error).__name__}: {error})"
            raise RegistryFormatError(msg) from error
        return cls(path, environments, claims)

    @classmethod
    @contextmanager
    def locked(cls, path: Path | None = None) -> Generator[Self]:
        """Hold an exclusive lock, yield the freshly loaded registry, and save on clean exit.

        Use this for every read-modify-write so concurrent `up` and `down` runs in different
        checkouts cannot lose each other's entries or claim the same slot.
        """
        path = path or registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with Path(f"{path}.lock").open("w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            registry = cls.load(path)
            yield registry
            registry.save()

    def entries(self) -> dict[str, Environment]:
        """Return a copy of the registered environments."""
        return dict(self._environments)

    def claimed_slot(self, key: str) -> int | None:
        """Return the slot a key holds, or `None` when it holds none, without claiming one."""
        claim = self._claims.get(key)
        return claim[0] if claim is not None else None

    def assign_slot(self, *, key: str, checkout: Path) -> int:
        """Reserve and return the slot for a key.

        Main always takes slot 0. A key that already has a claim keeps its slot when the same
        checkout asks again, or when the claiming checkout no longer exists on disk (the claim
        moves to the new checkout). Otherwise the lowest free slot is claimed.

        Args:
            key: Environment key.
            checkout: Checkout that owns the slot.

        Raises:
            SlotConflictError: If another checkout that still exists holds the key.
        """
        existing = self._claims.get(key)
        if existing is not None:
            slot, owner = existing
            if owner != checkout and owner.exists():
                msg = f"Key '{key}' is already used by checkout {owner}, not {checkout}"
                raise SlotConflictError(msg)
        elif key == MAIN_KEY:
            slot = 0
        else:
            taken = {claimed for claimed, _ in self._claims.values()}
            slot = 1
            while slot in taken:
                slot += 1
        self._claims[key] = (slot, checkout)
        return slot

    def upsert(self, env: Environment) -> None:
        """Add or replace an environment, creating its slot claim when none exists.

        Raises:
            ValueError: If the key already holds a claim on a different slot.
        """
        claim = self._claims.get(env.key)
        if claim is not None and claim[0] != env.slot:
            msg = f"Key '{env.key}' holds slot {claim[0]}, cannot register slot {env.slot}"
            raise ValueError(msg)
        self._claims[env.key] = (env.slot, env.checkout)
        self._environments[env.key] = env

    def remove(self, key: str) -> None:
        """Drop an environment and its slot claim. Unknown keys are ignored."""
        self._environments.pop(key, None)
        self._claims.pop(key, None)

    def save(self) -> None:
        """Write the registry atomically so readers never see a partial file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "description": DESCRIPTION,
            "slots": {
                key: {"slot": slot, "checkout": str(checkout)}
                for key, (slot, checkout) in sorted(self._claims.items())
            },
            "environments": {key: env.to_dict() for key, env in sorted(self._environments.items())},
        }
        # Entries carry raw API keys
        write_private(self.path, json.dumps(payload, indent=2) + "\n")

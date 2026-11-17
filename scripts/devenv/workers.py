"""Choose how many pytest-xdist workers `-n auto` starts on a developer machine."""

from collections.abc import Mapping

_OFF_VALUES = {"", "0", "false"}


def ci_is_on(environ: Mapping[str, str]) -> bool:
    """Report whether CI is set, with the same rule gate-cache uses, so every tool agrees.

    Args:
        environ: Environment to read CI from.

    Returns:
        bool: False when CI is unset, empty, "0", or "false" (any case), otherwise True.
    """
    return environ.get("CI", "").strip().lower() not in _OFF_VALUES


def auto_num_workers(environ: Mapping[str, str], cpu_count: int | None) -> int | None:
    """Leave a quarter of the cores free so the machine and the Docker test services stay responsive.

    Args:
        environ: Environment to read CI and an exported worker count from.
        cpu_count: Cores available to this process, or None when unknown.

    Returns:
        int | None: None to keep xdist's own count, which uses every core, in CI or when
            PYTEST_XDIST_AUTO_NUM_WORKERS is exported as a number. Otherwise the cores minus a
            quarter of them (at least one), with a minimum of two workers.
    """
    # xdist ignores a value that is not a number, so only a number may bypass the cap
    if environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS", "").strip().isdigit():
        return None
    if ci_is_on(environ):
        return None
    cores = cpu_count or 0
    return max(2, cores - max(1, cores // 4))

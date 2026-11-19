"""Start this checkout's test servers, then replace this process with pytest.

`duty test` wraps this script in gate-cache, so the servers start only when pytest runs:
on a tree that already passed, gate-cache skips the script and needs neither Docker nor the
servers.

Usage: python scripts/devenv/run_tests.py [PYTEST_ARGS...]
"""

import os
import subprocess
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
# Run by path, so sys.path starts with this directory, whose copy.py shadows the stdlib module.
# Replace it with the checkout so `scripts` imports as a package.
sys.path[0] = str(CHECKOUT)

from scripts.devenv import stack as devstack  # noqa: E402


def main(pytest_args: list[str]) -> None:
    """Start the test servers, point the suite at them, and exec pytest with the given arguments.

    Args:
        pytest_args: Arguments passed on to pytest unchanged.
    """
    try:
        docker = subprocess.run(["docker", "info"], capture_output=True, check=False)  # noqa: S607
    except FileNotFoundError:
        devstack.console.print("[red]`docker` was not found. Install it and try again.[/red]")
        raise SystemExit(1) from None
    if docker.returncode != 0:
        devstack.console.print("[red]Docker is not running. Start it and try again.[/red]")
        raise SystemExit(1)

    os.environ.update(devstack.run_task(devstack.start_test_services, cwd=CHECKOUT, claim=True))
    # The interpreter's own pytest, not the first on PATH, which can belong to another checkout
    pytest = str(Path(sys.executable).with_name("pytest"))
    os.execv(pytest, [pytest, *pytest_args])  # noqa: S606


if __name__ == "__main__":
    main(sys.argv[1:])

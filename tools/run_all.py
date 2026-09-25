#!/usr/bin/env python3
"""One gate, the same steps CI runs, in the same order. Stops at the first red one.

    tools/run-all.sh            staged files only, what a commit needs
    tools/run-all.sh --all      every tracked file, what CI checks on a push

Exit code 0 means every step passed. The step that fails ends the run right
there and its own exit code is passed through unchanged.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked(pattern):
    done = subprocess.run(["git", "ls-files", pattern], cwd=ROOT,
                          capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if line]


def find_tool(name):
    """A pinned local copy first, the same binary the workflow fetches, then PATH."""
    local = ROOT / "tools" / "local" / name
    if local.is_file():
        return str(local)
    return shutil.which(name)


def run(label, command):
    print("== %s ==" % label)
    result = subprocess.run(command, cwd=ROOT)
    print()
    if result.returncode != 0:
        print("%s failed, exit code %d. Stopping here." % (label, result.returncode))
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true",
                        help="check every tracked file instead of only what is staged")
    args = parser.parse_args()

    run("Privacy gate", [sys.executable, "tools/check-private.py"]
        + (["--all"] if args.all else []))

    py_files = ["abgal"] + tracked("*.py")
    run("Python compiles", [sys.executable, "-m", "py_compile"] + py_files)

    shellcheck = find_tool("shellcheck")
    if not shellcheck:
        print("shellcheck is not under tools/local/ and not on PATH.")
        print("Fetch it the way .github/workflows/checks.yml does, "
              "or: sudo apt-get install -y shellcheck")
        sys.exit(2)
    shell_files = tracked("*.sh") + tracked(".githooks/pre-commit")
    if not shell_files:
        print("No shell file matched. That is a broken pattern, not a clean tree.")
        sys.exit(1)
    run("ShellCheck", [shellcheck, "--severity=warning", "--shell=bash"] + shell_files)

    actionlint = find_tool("actionlint")
    if not actionlint:
        print("actionlint is not under tools/local/ and not on PATH.")
        print("Fetch it the way .github/workflows/checks.yml does.")
        sys.exit(2)
    run("actionlint", [actionlint, "-verbose"])

    venv_pytest = ROOT / ".venv" / "bin" / "pytest"
    pytest_cmd = str(venv_pytest) if venv_pytest.is_file() else (shutil.which("pytest") or "pytest")
    run("pytest", [pytest_cmd])

    print("All checks passed.")


if __name__ == "__main__":
    main()

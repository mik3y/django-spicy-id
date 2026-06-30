#!/usr/bin/env python3
"""Release helper: bump the version, stamp the changelog, and commit + tag it.

Usage:
    scripts/bump.py [patch|minor|major]

With no argument, the patch version is bumped. The script will:

  1. Increment the ``version`` in ``pyproject.toml``.
  2. Rename the pending changelog section ("## Current version ...") to the
     new version with today's date, and open a fresh pending section.
  3. Run pre-commit over the changed files.
  4. Commit the changes as "vX.Y.Z" and create a matching git tag.
"""

import datetime
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r'(?m)^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
PENDING_RE = re.compile(r"(?m)^## Current version.*$")
PENDING_HEADING = "## Current version (in development)"


def fail(msg):
    sys.exit(f"bump: error: {msg}")


def bump_version(major, minor, patch, part):
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def update_pyproject(part):
    text = PYPROJECT.read_text()
    match = VERSION_RE.search(text)
    if not match:
        fail(f"could not find a version line in {PYPROJECT.name}")
    major, minor, patch = (int(g) for g in match.groups())
    new = ".".join(str(n) for n in bump_version(major, minor, patch, part))
    text = VERSION_RE.sub(f'version = "{new}"', text, count=1)
    PYPROJECT.write_text(text)
    return new


def update_changelog(version):
    text = CHANGELOG.read_text()
    if not PENDING_RE.search(text):
        fail(f'could not find a "{PENDING_HEADING}" section in {CHANGELOG.name}')
    today = datetime.date.today().isoformat()
    released = f"## v{version} ({today})"
    # Open a fresh, empty pending section above the just-released one so the
    # next bump has somewhere to land.
    replacement = f"{PENDING_HEADING}\n\n{released}"
    CHANGELOG.write_text(PENDING_RE.sub(replacement, text, count=1))


def pre_commit_cmd():
    if shutil.which("pre-commit"):
        return ["pre-commit"]
    if shutil.which("uv"):
        return ["uv", "tool", "run", "pre-commit"]
    fail("pre-commit not found (install it or `uv tool install pre-commit`)")


def run(cmd, **kwargs):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, **kwargs)


def main():
    args = sys.argv[1:]
    part = args[0] if args else "patch"
    if part not in {"patch", "minor", "major"}:
        fail(f"unknown version part {part!r} (expected patch, minor, or major)")

    tag = None
    version = update_pyproject(part)
    tag = f"v{version}"

    existing = run(["git", "tag", "--list", tag], capture_output=True, text=True)
    if existing.stdout.strip():
        fail(f"tag {tag} already exists")

    update_changelog(version)

    files = [PYPROJECT.name, CHANGELOG.name]
    run(["git", "add", *files])

    # Run pre-commit; if it reformats files, re-stage and run once more.
    pc = pre_commit_cmd()
    result = run([*pc, "run", "--files", *files])
    if result.returncode != 0:
        run(["git", "add", *files])
        result = run([*pc, "run", "--files", *files])
        if result.returncode != 0:
            fail("pre-commit failed; fix the issues and re-run bump")
    run(["git", "add", *files])

    run(["git", "commit", "-m", tag], check=True)
    run(["git", "tag", tag], check=True)
    print(f"\nbump: created commit and tag {tag}")
    print("Review it, then `git push && git push --tags` when ready.")


if __name__ == "__main__":
    main()

# Maintainer notes

Notes for maintainers of `django-spicy-id`. If you are just using the library, see the [README](../README.md).

## Releasing

To cut a new release, run the `bump` tool:

```
make bump       # bumps the patch version (default)
make bump minor # bumps the minor version
make bump major # bumps the major version
```

Equivalently, you can call the script directly:

```
./scripts/bump.py [patch|minor|major]
```

`bump` will:

1. Increment `version` in `pyproject.toml` (patch by default).
2. Stamp the pending changelog section (`## Current version ...`) in `CHANGELOG.md` with the new version and today's date, and open a fresh pending section for the next release.
3. Run `pre-commit` over the changed files (re-staging anything it reformats).
4. Create a commit named `vX.Y.Z` and a matching git tag.

Nothing is pushed automatically. Review the commit and tag, then `git push && git push --tags` when you're happy.

Pushing the tag triggers the `Publish` workflow, which builds the package, creates a GitHub release, and uploads to PyPI using the `PYPI_PASSWORD` repository secret.

## API reference

`docs/api.md` is generated from the library's public docstrings by `scripts/gen_api_docs.py` (configured in `pydoc-markdown.yml`). Docstrings are the single source of truth; do not hand-edit `docs/api.md`.

```
make apidocs    # regenerate docs/api.md
```

A pre-commit hook runs the generator in `--check` mode, so the file cannot drift from the docstrings.

## Table of contents

The README's table of contents is generated with [doctoc](https://github.com/thlorenz/doctoc):

```
make toc
```

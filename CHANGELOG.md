# Changelog

## Current version (in development)

* Feature: Added `TypeIDField`, a [TypeID](https://github.com/jetify-com/typeid)-compatible spicy id (UUIDv7 in Crockford base32 with a lowercase snake_case prefix) backed by a `UUIDField` column. Validated against the TypeID spec's official conformance vectors.
* Feature: Added the `ENCODING_BASE_32` (Crockford base32) encoding and the `uuid7()` helper.
* Deprecation: `SpicySmallAutoField` is deprecated and will be removed in v2.0.0. Use `SpicyAutoField` instead.
* Deprecation: `SpicyUUIDField` is deprecated and will be removed in v2.0.0. Use `TypeIDField` instead.
* Docs: Added a generated API reference (`docs/api.md`), rendered from the public docstrings with pydoc-markdown (`make apidocs`) and kept in sync by a pre-commit hook.
* Internal: Replaced the unused `sphinx` dev dependency with `pydoc-markdown`, and added a `pre-commit` CI workflow that runs all hooks.

## v1.1.0 (2026-07-01)

* Feature: Added `SpicyUUIDField`, a spicy id backed by a `UUIDField` column.
* Bugfix: Fix `full_clean()` raising `TypeError` on models with spicy id fields.
* Bugfix: `to_python()` now raises `ValidationError` instead of `ProgrammingError` for invalid values, matching Django's field contract.
* Bugfix: `from django_spicy_id import *` no longer raises `TypeError`.
* Bugfix: Field prefixes containing hyphens are now correctly rejected, as documented.
* Bugfix: Enforce the valid id range — ids that decode outside the field's bounds are rejected up front with a clear error instead of failing at the database, and the full range is usable (including the maximum value and `0`).
* Bugfix: A failed save no longer replaces a `SpicyUUIDField` value with a raw `UUID` on the in-memory instance.
* Breaking change: Drop support for Python 3.10 and 3.11. Python 3.12+ is now required.
* Breaking change: Drop support for Django 3.2. Django 4.2+ is now required.
* Add support for Python 3.13 and 3.14.
* Add support for Django 5.2 and 6.0.
* Internal: Switch Python code formatter/linter to [ruff](https://docs.astral.sh/ruff/).
* Internal: Switch to [uv](https://docs.astral.sh/uv/) for project management.

## v1.0.0 (2023-12-25)

* Feature: Added `monkey_patch_drf()` utility.

## v0.7.0 (2023-08-23)

This version fixes a bug that affects Django 3.x installations and is recommended for those users.

* Bugfix: Add workaround for a Django 3.x bug where a newly-saved instance's `.id` might be returned as a number, not a spicy string. (#6)
* Breaking change: Dropped support for Django 2.2.
* Updated target Django versions from `3.1 -> 3.2` and `4.1 -> 4.2`.
* Updated integration tests to properly test against all Django versions (#7).

## v0.6.1 (2023-08-20)

* Repackage of previous release. No code changes compared to `v0.6.0`.

## v0.6.0 (2023-08-20)

* Breaking change: Bug fix: The `randomize` feature will set `.id` to a string, not a number, when the instance is created.

## v0.5.0 (2023-08-06)

* Breaking change: Fixed bug causing `SpicyAutoField` and `SpicySmallAutoField` to inherit from `models.BigAutoField`.

## v0.4.0 (2023-06-23)

* Feature: Add and document the `get_url_converter()` helper.
* Feature: Add and document the `.re_pattern` attribute.

## v0.3.1 (2022-12-14)

* bugfix: fix an error with prefixes greater than 2 characters (:facepalm:)

## v0.3.0 (2022-12-14)

* Breaking change: Providing both `default` and `randomize` is not alowed.
* Breaking change: Illegal values now throw `django.db.utils.ProgrammingError`
* The `randomize` feature now uses the `secrets` module.
* Fields now expose `.re` and `.validate_string(strval)` to assist with validation.
* Symbols are now exported from the top-level `django_spicy_id` module.

## v0.2.2 (2022-12-14)

* First official release.

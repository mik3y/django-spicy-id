# Changelog

## Current version (in development)

* Internal: Switch Python code formatter/linter to [ruff](https://docs.astral.sh/ruff/).
* Internal: Drop support for Python 3.9.

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

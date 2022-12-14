# Changelog

## Current version (in development)

* Breaking change: Providing both `default` and `randomize` is not alowed.
* Breaking change: Illegal values now throw `django.db.utils.ProgrammingError`
* The `randomize` feature now uses the `secrets` module.
* Fields now expose `.re` and `.validate_string(strval)` to assist with validation.

## v0.2.2 (2022-12-14)

* First official release.

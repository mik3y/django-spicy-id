# Changelog

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

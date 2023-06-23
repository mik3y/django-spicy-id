# django-spicy-id

A drop-in replacement for Django's `AutoField` that gives you "Stripe-style" self-identifying string object IDs, like `user_1234`.

**Status:** Experimental! No warranty. See `LICENSE.txt`.

[![PyPI version](https://badge.fury.io/py/django-spicy-id.svg)](https://badge.fury.io/py/django-spicy-id)
[![PyPI Supported Python Versions](https://img.shields.io/pypi/pyversions/django-spicy-id.svg)](https://pypi.python.org/pypi/django-spicy-id/) ![Test status](https://github.com/mik3y/django-spicy-id/actions/workflows/test.yml/badge.svg)

## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [What is a "spicy" id?](#what-is-a-spicy-id)
- [_Why_ use spicy ids?](#_why_-use-spicy-ids)
- [Installation](#installation)
  - [Requirements](#requirements)
  - [Instructions](#instructions)
- [Usage](#usage)
  - [Field types](#field-types)
  - [Required Parameters](#required-parameters)
  - [Optional Parameters](#optional-parameters)
  - [Registering URLs](#registering-urls)
  - [Field Attributes](#field-attributes)
    - [`.validate_string(strval)`](#validate_stringstrval)
    - [`.re`](#re)
    - [`.re_pattern`](#re_pattern)
  - [Utility methods](#utility-methods)
    - [`get_url_converter(model_class, field_name)`](#get_url_convertermodel_class-field_name)
  - [Errors](#errors)
    - [`django.db.utils.ProgrammingError`](#djangodbutilsprogrammingerror)
    - [`django_spicy_id.MalformedSpicyIdError`](#django_spicy_idmalformedspicyiderror)
- [Tips and tricks](#tips-and-tricks)
  - [Don't change field configuration](#dont-change-field-configuration)
- [Changelog](#changelog)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## What is a "spicy" id?

It's a made-up name (because I couldn't think of a better one) for a numeric primary keys type that is shown and manipulated as a string, prefixed with a constant value.

Here are some examples. You can use this library to make your Django row IDs look like:

- `user_1234`
- `account-00000000deadbeef`
- `bloop:1a2k3841x`

Although you should always treat these values as opaque and _never_ decode or parse the string's contents elsewhere (see _Errors_), you can think of every spicy id as being composed of:

```
<prefix> <separator> <encoded_value>
```

- **`prefix`**: A fixed string value that will be the same for all IDs of this record type, forever.
- **`separator`**: A configurable separator which, like `prefix`, is fixed forever; usually `_` (the default) or `-` (another popular choice).
- **`encoded_value`**: The numeric portion of the id. This library supports using base 16 (hex) or base 62.

Importantly, the underlying database value is still stored and retrieved as a _numeric type_, just like an `AutoField`, `SmallAutoField`, or `BigAutoField`.

## _Why_ use spicy ids?

Briefly: Because they're so much nicer for humans to work with.

- **Readability:** While row-level primary keys are typically treated as "anonymous" (as in "not something anyone should have to care about"), the fact is these values still _show up_ in lots of situations: They're in URLs, dumped in logfiles, shown in queries, and so on. In these situations, it's just plain faster to understand "what am I looking at" when the identifier itself tells you its type.
- **Conflict and accident prevention:** When your systems require you to pass around typed identifiers like `acct_1234` and `invoice_5432beef`, certain kinds of accidents become impossible. For example, `HTTP DELETE /users/invoice_21` fails fast.
- **Future-proofing:** Adopting spicy IDs means your systems and APIs are developed to accept a basically-opaque string as an ID. While their underlying type is numeric, in very advanced situations you may be able to migrate to a different type or datastore "behind" the abstraction the string ID creates.

For a more detailed look at this pattern, see Stripe's ["Object IDs: Designing APIs for Humans"](https://dev.to/stripe/designing-apis-for-humans-object-ids-3o5a).

## Installation

### Requirements

This package supports and is tested against the latest patch versions of:

- **Python:** 3.8, 3.9, 3.10, 3.11
- **Django:** 2.2, 3.1, 4.1
- **MySQL:** 5.7, 8.0
- **PostgreSQL:** 9.5, 10, 11, 12
- **SQLite:** 3.9.0+

All database backends are tested with the latest versions of their drivers. SQLite is also tested on GitHub Actions' latest macOS virtual environment.

### Instructions

```
pip install django_spicy_id
```

## Usage

Given the following example model:

```py
from django.db import models
from django_spicy_id import SpicyBigAutoField

class User(models.model):
    id = SpicyBigAutoField(primary_key=True, prefix='usr')
```

Example usage:

```py
>>> u = models.User.objects.create()
>>> u.id
'usr_1'
>>> u2 = models.User.objects.create(id=123456789)
>>> u2.id
'usr_8M0kX'
>>> found_user = models.User.objects.filter(id='usr_8M0kX').first()
>>> found_user == u2
True
```

### Field types

- `SpicyBigAutoField`: A spicy id which is backed by a `BigAutoField` (i.e. 64-bit int) column.
- `SpicyAutoField`: A spicy id which is backed by a `AutoField` (i.e. 32-bit int) column.
- `SpicySmallAutoField`: A spicy id which is backed by a `SmallAutoField` (i.e. 16-bit int) column.

### Required Parameters

The following parameters are required at declaration:

* **`prefix`**: The prefix to use in the encoded form. Typically this is a short, descriptive string, like `user` or `acct` and similar. **Note:** This library does not ensure the string you provide is unique within your project. You should ensure of that.

### Optional Parameters

In addition to all parameters you can provide a normal `AutoField`, each of the field types above supports the following additional optional paramters:

- **`encoding`**: What numeric encoding scheme to use. One of `django_spicy_id.ENCODING_BASE_62` (default), `django_spicy_id.ENCODING_BASE_58`, or `django_spicy_id.ENCODING_HEX`.
- **`sep`**: The separator character. Defaults to `_`. Can be any string.
- **`pad`**: Whether the encoded portion of the id should be zero-padded so that all values are the same string length. Either `False` (default) or `True`.
  - Example without padding: `user_8M0kX`
  - Example with padding: `user_0000008M0kX`
- **`randomize`**: If `True`, the default value of a new record will be generated randomly using `secrets.randbelow()`. If `False` (the default), works just like a normal `AutoField` i.e. the default value comes from the database upon `INSERT`.
  - When `randomize` is set, an error will be thrown if `default` is also set, since `randomize` is essentially a special and built-in `default` function.
  - If you use this feature, be aware of its hazards: 
      - The generated ID may conflict with an existing row, with probability [determined by the birthday problem](https://en.wikipedia.org/wiki/Birthday_problem#Probability_table) (i.e. the column size and the size of the existing dataset).
      - A conflict can also arise if two processes generate the same value for `secrets.randbelow()` (i.e. if system entropy is identical or misconfigured for some reason).

### Registering URLs

When installing routes that must match a specific spicy id, you can use the `get_url_converter()` helper method to install a Django [custom path converter](https://docs.djangoproject.com/en/3.2/topics/http/urls/#registering-custom-path-converters).

Using this method will ensure that _only_ valid spicy ID strings for that field will be presented to your view.

Example:

```py
# models.py
class User(models.model):
    id = SpicyBigAutoField(primary_key=True, prefix='usr')
```

```py
# urls.py
from . import models
from django.urls import path, register_converter
from django_spicy_id import get_url_converter

# Register the pattern for `User.id` as "spicy_user_id". You should do this
# once for each unique spicy ID field.
register_converter(get_url_converter(models.User, 'id'), 'spicy_user_id')

urlpatterns = [
    path('users/<spicy_user_id:id>', views.user_detail),
    ...
]
```

```py
# views.py

def user_detail(request, id):
  user = models.User.objects.get(id=id)
  ...
```

### Field Attributes

The following attributes are available on the field once constructed

#### `.validate_string(strval)`

Checks whether `strval` is a legal value for the field, throwing `django_spicy_id.errors.MalformedSpicyIdError` if not.

#### `.re`

A compiled regex which can be used to validate a string.

#### `.re_pattern`

A string regex pattern which can be used to validate a string. Unlike the pattern used in `re`, this pattern does not include the leading `^` and trailing `$` boundary characters, making it easier to use in things like Django url patterns.

You probably don't need to use this directly, instead see `get_url_converter()`.

### Utility methods

These utility methods are provided on the top-level `django_spicy_id` module.

#### `get_url_converter(model_class, field_name)`

Returns a Django [custom path converter](https://docs.djangoproject.com/en/3.2/topics/http/urls/#registering-custom-path-converters) for `field_name` on `model_class`.

See [Registering URLs](#registering-urls) for example usage.

### Errors

#### `django.db.utils.ProgrammingError`

Thrown when attempting to access or query this field using an illegal value. Some examples of this situation:

* Providing a spicy id with the wrong prefix or separator (e.g `id="acct_1234"` where `id="invoice_1234"` is expected).
* Providing a string with illegal characters in it (i.e. where the encoded part isn't decodable)
* Providing an unpadded value when padding is enabled.
* Providing a padded value when padded is disabled.

You can consider these situations analogous to providing a wrongly-typed object to any other field type, for example `SomeModel.objects.filter(id=object())`.

You can avoid this situation by validating inputs first. See _Field Attributes_.

**🚨 Warning:** Regardless of field configuration, the string value of a spicy id must **always** be treated as an _exact value_. Just like you would never modify the contents of a `UUID4`, a spicy id string must never be translated, re-interpreted, or changed by a client.

#### `django_spicy_id.MalformedSpicyIdError`

A subclass of `ValueError`, raised by `.validate_string(strval)` when the provided string is invalid for the field's configuration.

## Tips and tricks

### Don't change field configuration

Changing `prefix`, `sep`, `pad`, or `encoding` after you have started using the field should be considered a _breaking change_ for any external callers.

Although the stored row IDs are never changed, any spicy IDs generated previously, with a different encoding configuration, may now be invalid or (potentially catastrophically) resolve to a different object.

For just one example, `user_10` would naturally refer to a different numeric row id if parsed as `hex` versus `base62` or `base58`. You should avoid changing the field configuration.

## Changelog

See [`CHANGELOG.md`](https://github.com/mik3y/django-spicy-id/blob/main/CHANGELOG.md) for a summary of changes.
# django-spicy-id

A drop-in replacement for Django's `AutoField` that gives you "Stripe-style" self-identifying string object IDs, like `user_1234`.

**Status:** Experimental! No warranty. See `LICENSE.txt`.

<!-- ![Lint status](https://github.com/mik3y/django-spicy-id/actions/workflows/lint.yml/badge.svg)
![Test status](https://github.com/mik3y/django-spicy-id/actions/workflows/test.yml/badge.svg)
 -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [What is a "spicy" id?](#what-is-a-spicy-id)
- [_Why_ use spicy ids?](#_why_-use-spicy-ids)
- [Usage](#usage)
  - [Field types](#field-types)
  - [Required Parameters](#required-parameters)
  - [Optional Parameters](#optional-parameters)
  - [Errors](#errors)
- [Installation](#installation)
  - [Requirements](#requirements)
  - [Instructions](#instructions)

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

## Usage

Given the following example model:

```py
from django.db import models
from django_spicy_id.fields import SpicyBigAutoField

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

- **`sep`**: The separator character. Defaults to `_`. Can be any string.
- **`encoding`**: What numeric encoding scheme to use. One of `fields.ENCODING_BASE_62`, `fields.ENCODING_BASE_58`, or `fields.ENCODING_HEX`.
- **`pad`**: Whether the encoded portion of the id should be zero-padded so that all values are the same string length. Either `False` (default) or `True`.
  - Example without padding: `user_8M0kX`
  - Example with padding: `user_0000008M0kX`
- **`randomize`**: If `True`, the default value for creates will be chosen from `random.randrange()`. If `False` (the default), works just like a normal `AutoField` i.e. the default value comes from the database upon `INSERT`.

**Warning:** Changing `prefix`, `sep`, `pad`, or `encoding` after you have started using the field is a _breaking change_. IDs generated with a different configuration will be rejected. You should not do this.

### Errors

The field will throw `django_spicy_id.errors.MalformedSpicyIdError`, a subclass of `ValueError`, when an "illegal" string is provided. Note that this error can happen at runtime.

Some examples of situations that will throw this error:

* Querying a spicy id with the wrong prefix or separator (e.g `id="acct_1234` where `id=invoice_1234` is expected).
* Using illegal characters in the string.
* Providing an unpadded value when padding is enabled.
* Providing a padded value when padded is disabled.

Take special note of the last two errors: Regardless of field configuration the string value a spicy id yields must **always** be treated as an _exact value_. Just like you would never modify a `UUID4`, a spicy id string should never be translated, re-interpreted, or changed by a client.

## Installation

### Requirements

This package supports and is tested against the latest patch versions of:

- **Python:** 3.8, 3.9, 3.10, 3.11
- **Django:** 2.2, 3.0, 3.1, 4.0
- **MySQL:** 5.7, 8.0
- **PostgreSQL:** 9.5, 10, 11, 12
- **SQLite:** 3.9.0+

All database backends are tested with the latest versions of their drivers. SQLite is also tested on GitHub Actions' latest macOS and Windows virtual environments.

### Instructions

Coming soon: pypi distribution. Then you will be able to do...

```
pip install django_spicy_id
```

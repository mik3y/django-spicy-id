import math
import re
import secrets

import django
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.signals import post_save
from django.db.utils import ProgrammingError

from django_spicy_id.errors import MalformedSpicyIdError

from . import baseconv

# Encoding strategies which may be selected with the `encoding=` field parameter.
ENCODING_HEX = "hex"
ENCODING_BASE_58 = "b58"
ENCODING_BASE_62 = "b62"

# Maps encoding strategy to its encoder/decoder.
CODECS_BY_ENCODING = {
    ENCODING_HEX: baseconv.base16,
    ENCODING_BASE_58: baseconv.base58,
    ENCODING_BASE_62: baseconv.base62,
}

# Validates acceptable values for the `prefix=` field parameter.
LEGAL_PREFIX_RE = re.compile("^[a-zA-Z][0-9a-z-A-Z]*$")


def get_regex(preamble, codec, pad, char_len):
    """Returns a regex that validates a spicy id with with given parameters.

    If `pad` is True, the regex allows leading padding characters (a
    zero in most codecs). Else, these are not allowed.
    """
    digits = codec.digits
    digits_without_pad_char = digits[1:]
    escaped_preamble = re.escape(preamble)
    if not pad:
        trailer_len = char_len - 1
        return re.compile(
            f"^({escaped_preamble})([{digits_without_pad_char}][{digits}]{{,{trailer_len}}})$"
        )
    else:
        return re.compile(f"^({escaped_preamble})([{digits}]{{{char_len}}})$")


class BaseSpicyAutoField(models.Field):
    """An AutoField that is rendered as a prefixed string."""

    NUM_BITS = None  # Must be defined in subclasses.

    def __init__(
        self,
        prefix,
        sep="_",
        encoding=ENCODING_BASE_62,
        randomize=False,
        pad=False,
        *args,
        **kwargs,
    ):
        if not self.NUM_BITS:
            raise NotImplemented(
                "attempt to init abstract base class, or subclass has failed to set NUM_BITS"
            )
        if encoding not in CODECS_BY_ENCODING:
            raise ImproperlyConfigured(f'unknown encoding "{encoding}"')
        if not isinstance(prefix, str):
            raise ImproperlyConfigured("prefix must be a string")
        if not isinstance(sep, str):
            raise ImproperlyConfigured("sep must be a string")
        if not sep.isascii():
            raise ImproperlyConfigured("sep must be ascii")
        if not LEGAL_PREFIX_RE.match(prefix):
            raise ImproperlyConfigured(
                "prefix: only ascii numbers and letters allowed, must start with a letter"
            )
        if randomize and kwargs.get("default"):
            raise ImproperlyConfigured("cannot provide both `randomize` and `default`")

        self.prefix = prefix
        self.sep = sep
        self.randomize = randomize
        self.pad = pad

        if randomize:
            # Inject our default value generator when `randomize` is enabled.
            # Note that this must be stripped in `deconstruct()` so migrations don't
            # get generated with the default function.
            kwargs["default"] = lambda: self._new_random_id()

        self.encoding = encoding
        self.codec = CODECS_BY_ENCODING[self.encoding]
        self.max_value = 2 ** (self.NUM_BITS - 1) - 1
        self.max_characters = math.ceil(math.log(self.max_value, len(self.codec.digits)))
        self.re = get_regex(f"{self.prefix}{self.sep}", self.codec, self.pad, self.max_characters)

        # Expose the re pattern without word boundaries, for use in places where they
        # would interfere (like urlpatterns).
        #
        # TODO(mikey): Expose `.as_converter()`, generating a Django URLpatterns converter
        # class, as a further convenience.
        # Ref: https://docs.djangoproject.com/en/4.1/topics/http/urls/#registering-custom-path-converters
        self.re_pattern = self.re.pattern[1:-1]

        super().__init__(*args, **kwargs)

    def _to_string(self, intvalue):
        encoded = self.codec.encode(intvalue)
        unpadded_len = len(encoded)
        if self.pad and unpadded_len < self.max_characters:
            pad_char = self.codec.digits[0]
            encoded = pad_char * (self.max_characters - unpadded_len) + encoded

        return f"{self.prefix}{self.sep}{encoded}"

    def _new_random_id(self):
        return self._to_string(self._generate_random_default_value())

    def _generate_random_default_value(self):
        """Generates a random value on the range [1, self.max_value)."""
        return 1 + secrets.randbelow(self.max_value - 1)

    def _validate_string_internal(self, s):
        if not isinstance(s, str):
            raise MalformedSpicyIdError("value must be a string")
        if not s:
            raise MalformedSpicyIdError("value must be non-empty")
        m = self.re.match(s)
        if not self.re.match(s):
            raise MalformedSpicyIdError(
                f"value does not match expected regex {repr(self.re.pattern)}"
            )
        _, encoded = m.groups()
        return encoded

    def validate_string(self, strval):
        """Utility function to validate any string against this field's config.

        Raises `MalformedSpicyIdError` on any error. Returns
        """
        # Implemented by wrapping `_validate_string_internal` and stripping away the
        # return value, because we need access to the retval internally (but don't
        # want public clients to depend on it).
        self._validate_string_internal(strval)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return self._to_string(value)

    def get_prep_value(self, value):
        if not value:
            return super().get_prep_value(value)
        elif isinstance(value, int):
            return super().get_prep_value(value)
        try:
            encoded = self._validate_string_internal(value)
            return self.codec.decode(encoded)
        except MalformedSpicyIdError as e:
            raise ProgrammingError(f"the value {repr(value)} is not valid: {e}")

    def to_python(self, value):
        if not value:
            return super().to_python(value)
        elif isinstance(value, str) and self.re.match(value):
            return value
        elif isinstance(value, int):
            return self._to_string(value)
        raise ProgrammingError(f"The value {repr(value)} is not valid for this field")

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["prefix"] = self.prefix
        kwargs["sep"] = self.sep
        kwargs["encoding"] = self.encoding
        kwargs["pad"] = self.pad
        kwargs["randomize"] = self.randomize
        if kwargs["randomize"] and "default" in kwargs:
            # Keep our built-in `default` function hidden from migrations, etc., when
            # the higher-level feature `randomize` is enabled.
            del kwargs["default"]
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)

        # Special case: Register a signal handler when this row is created.
        # Workaround for issue #6 / Django issue 32442.
        #
        # When the DB connection does not support `can_return_columns_from_insert`,
        # the raw row value is returned by Django on insert. This causes the caller
        # to receive a numeric value when the row is inserted, due to the upstream
        # bug (value does flow through `Field.from_db_value()`).
        #
        # https://code.djangoproject.com/ticket/32442

        # Not needed in Django >= 4.
        if django.VERSION >= (4, 0):
            return

        # Only affects primary keys.
        if not self.primary_key:
            return

        def spicy_id_create_handler(sender, instance, created, raw, **kwargs):
            if not created or raw:
                return
            nonlocal name
            val = getattr(instance, name)
            if isinstance(val, int):
                setattr(instance, name, self.to_python(val))

        post_save.connect(spicy_id_create_handler, sender=cls, weak=False)


class SpicyBigAutoField(BaseSpicyAutoField, models.BigAutoField):
    """A Spicy ID field that is backed by a standard 64-bit Django BigAutoField."""

    NUM_BITS = 64


class SpicyAutoField(BaseSpicyAutoField, models.AutoField):
    """A Spicy ID field that is backed by a standard 32-bit Django AutoField."""

    NUM_BITS = 32


class SpicySmallAutoField(BaseSpicyAutoField, models.SmallAutoField):
    """A Spicy ID field that is backed by a standard 16-bit Django SmallAutoField."""

    NUM_BITS = 16

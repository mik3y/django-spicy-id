import math
import random
import re

from django.core.exceptions import ImproperlyConfigured
from django.db import models

from django_spicy_id.errors import MalformedSpicyIdError

from . import baseconv

ENCODING_HEX = "hex"
ENCODING_BASE_58 = "b58"
ENCODING_BASE_62 = "b62"

CODECS_BY_ENCODING = {
    ENCODING_HEX: baseconv.base16,
    ENCODING_BASE_58: baseconv.base58,
    ENCODING_BASE_62: baseconv.base62,
}

LEGAL_PREFIX_RE = re.compile("^[a-zA-Z][0-9a-z-A-Z]?$")


def get_regex(preamble, codec, pad, char_len):
    """Builder function

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


class BaseSpicyAutoField(models.BigAutoField):
    """An auto field that is rendered as a prefixed string."""

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

        self.prefix = prefix
        self.sep = sep
        self.randomize = randomize
        self.pad = pad

        self.encoding = encoding
        self.codec = CODECS_BY_ENCODING[self.encoding]
        self.max_value = 2 ** (self.NUM_BITS - 1) - 1
        self.max_characters = math.ceil(math.log(self.max_value, len(self.codec.digits)))
        self.re = get_regex(f"{self.prefix}{self.sep}", self.codec, self.pad, self.max_characters)

        super().__init__(*args, **kwargs)

    def _to_string(self, intvalue):
        encoded = self.codec.encode(intvalue)
        unpadded_len = len(encoded)
        if self.pad and unpadded_len < self.max_characters:
            pad_char = self.codec.digits[0]
            encoded = pad_char * (self.max_characters - unpadded_len) + encoded

        return f"{self.prefix}{self.sep}{encoded}"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return self._to_string(value)

    def get_prep_value(self, value):
        if value is None and self.randomize:
            value = random.randrange(1, self.max_value)
            return value
        if value is None or isinstance(value, int):
            return super().get_prep_value(value)
        m = self.re.match(value)
        if not m:
            raise MalformedSpicyIdError(f'Value "{value}" does not match {self.re}')
        _, encoded = m.groups()
        return self.codec.decode(encoded)

    def to_python(self, value):
        if not value:
            return super().to_python(value)
        elif isinstance(value, str) and self.re.match(value):
            return value
        elif isinstance(value, int):
            return self._to_string(value)
        raise MalformedSpicyIdError(f"Bad value: ${value}")

    def has_default(self):
        if self.randomize:
            return True
        return super().has_default()

    def get_default(self):
        if self.randomize:
            value = random.randrange(1, self.max_value)
            return value
        return super().get_default()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["prefix"] = self.prefix
        kwargs["sep"] = self.sep
        kwargs["encoding"] = self.encoding
        kwargs["randomize"] = self.randomize
        kwargs["pad"] = self.pad
        return name, path, args, kwargs


class SpicyBigAutoField(BaseSpicyAutoField, models.BigAutoField):
    NUM_BITS = 64


class SpicyAutoField(BaseSpicyAutoField, models.AutoField):
    NUM_BITS = 32


class SpicySmallAutoField(BaseSpicyAutoField, models.SmallAutoField):
    NUM_BITS = 16

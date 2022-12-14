import math
import random
import re

from django.db import models

from . import baseconv


class BaseSpicyAutoField(models.BigAutoField):
    """An auto field that is rendered as a prefixed string."""

    NUM_BITS = 64
    ENCODING_HEX = "hex"
    ENCODING_BASE_62 = "b62"

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
        self.prefix = prefix
        self.sep = sep
        self.encoding = encoding
        self.randomize = randomize
        self.pad = pad
        self.max_value = 2 ** (self.NUM_BITS - 1) - 1

        if self.encoding == self.ENCODING_HEX:
            self.max_characters = math.ceil(math.log(self.max_value, 16))
            self.re = re.compile(f"^({self.prefix}){self.sep}([0-9a-f]{{,{self.max_characters}}})$")
        elif self.encoding == self.ENCODING_BASE_62:
            self.max_characters = math.ceil(math.log(self.max_value, 62))
            self.re = re.compile(
                f"^({self.prefix}){self.sep}([0-9a-zA-Z]{{,{self.max_characters}}})$"
            )
        else:
            raise ValueError(f"Unknown encoding: {self.encoding}")

        super().__init__(*args, **kwargs)

    def _to_string(self, intvalue):
        if self.encoding == self.ENCODING_BASE_62:
            encoded = baseconv.base62.encode(intvalue)
        elif self.encoding == self.ENCODING_HEX:
            encoded = baseconv.base16.encode(intvalue).lower()

        unpadded_len = len(encoded)
        if self.pad and unpadded_len < self.max_characters:
            encoded = "0" * (self.max_characters - unpadded_len) + encoded

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
            raise ValueError(f'Value "{value}" does not match {self.re}')
        _, encoded = m.groups()
        if self.encoding == self.ENCODING_HEX:
            return int(encoded, 16)
        else:
            return baseconv.base62.decode(encoded)

    def to_python(self, value):
        if not value:
            return super().to_python(value)
        elif isinstance(value, str) and self.re.match(value):
            return value
        elif isinstance(value, int):
            return self._to_string(value)
        raise ValueError(f"Illegal value: ${value}")

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

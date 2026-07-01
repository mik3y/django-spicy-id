import re
import secrets
import uuid

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.db.utils import ProgrammingError
from django.utils.functional import cached_property

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
LEGAL_PREFIX_RE = re.compile("^[a-zA-Z][0-9a-zA-Z]*$")


def num_digits(value, base):
    """Returns the exact number of base-`base` digits needed to represent `value`.

    Uses integer arithmetic rather than `math.log`, which can be off by one near
    powers of the base due to floating-point rounding.
    """
    digits = 1
    while value >= base:
        value //= base
        digits += 1
    return digits


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
            raise NotImplementedError(
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
        self.max_characters = num_digits(self.max_value, len(self.codec.digits))
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
        """Generates a random value on the range [1, self.max_value]."""
        return 1 + secrets.randbelow(self.max_value)

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
        # The regex bounds the character length, but a max-length string can still
        # decode to a value larger than the backing column can hold. Enforce the
        # numeric range here so out-of-range ids are rejected before reaching the DB.
        value = self.codec.decode(encoded)
        if not 0 <= value <= self.max_value:
            raise MalformedSpicyIdError(
                f"decoded value {value} is out of range (must be 0..{self.max_value})"
            )
        return encoded

    def validate_string(self, strval):
        """Utility function to validate any string against this field's config.

        Raises `MalformedSpicyIdError` on any error. Returns
        """
        # Implemented by wrapping `_validate_string_internal` and stripping away the
        # return value, because we need access to the retval internally (but don't
        # want public clients to depend on it).
        self._validate_string_internal(strval)

    def _validate_spicy_id(self, value):
        """Django validator for spicy id string values."""
        try:
            self._validate_string_internal(value)
        except MalformedSpicyIdError as e:
            raise ValidationError(str(e), code="invalid")

    @cached_property
    def validators(self):
        # For integer values, defer to the parent IntegerField validators
        # (min/max range checks). For string values, validate the spicy id
        # format (prefix, separator, encoding, padding) and decoded numeric range.
        parent_validators = super().validators

        def spicy_id_validator(value):
            if isinstance(value, int):
                for v in parent_validators:
                    v(value)
            elif isinstance(value, str):
                self._validate_spicy_id(value)

        return [spicy_id_validator]

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
            self._validate_spicy_id(value)  # also enforces the numeric range
            return value
        elif isinstance(value, int):
            return self._to_string(value)
        raise ValidationError(
            f"The value {repr(value)} is not valid for this field",
            code="invalid",
        )

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

class SpicyBigAutoField(BaseSpicyAutoField, models.BigAutoField):
    """A Spicy ID field that is backed by a standard 64-bit Django BigAutoField."""

    NUM_BITS = 64


class SpicyAutoField(BaseSpicyAutoField, models.AutoField):
    """A Spicy ID field that is backed by a standard 32-bit Django AutoField."""

    NUM_BITS = 32


class SpicySmallAutoField(BaseSpicyAutoField, models.SmallAutoField):
    """A Spicy ID field that is backed by a standard 16-bit Django SmallAutoField."""

    NUM_BITS = 16


class SpicyUUIDField(models.UUIDField):
    """A UUIDField that is rendered as a prefixed, encoded string."""

    def __init__(
        self,
        prefix,
        sep="_",
        encoding=ENCODING_BASE_62,
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
        self.encoding = encoding
        self.codec = CODECS_BY_ENCODING[self.encoding]

        max_value = 2**128 - 1
        self.max_characters = num_digits(max_value, len(self.codec.digits))
        self.re = get_regex(f"{self.prefix}{self.sep}", self.codec, False, self.max_characters)
        self.re_pattern = self.re.pattern[1:-1]

        kwargs.setdefault("default", uuid.uuid4)
        super().__init__(*args, **kwargs)

    def _to_string(self, uid):
        if not isinstance(uid, uuid.UUID):
            uid = uuid.UUID(uid) if isinstance(uid, str) else uuid.UUID(int=uid)
        encoded = self.codec.encode(uid.int)
        return f"{self.prefix}{self.sep}{encoded}"

    def _validate_string_internal(self, s):
        if not isinstance(s, str):
            raise MalformedSpicyIdError("value must be a string")
        if not s:
            raise MalformedSpicyIdError("value must be non-empty")
        m = self.re.match(s)
        if not m:
            raise MalformedSpicyIdError(
                f"value does not match expected regex {repr(self.re.pattern)}"
            )
        _, encoded = m.groups()
        # A max-length string can decode above the 128-bit UUID range; reject it
        # here rather than letting `uuid.UUID(int=...)` raise deep in the stack.
        value = self.codec.decode(encoded)
        if not 0 <= value < 2**128:
            raise MalformedSpicyIdError(
                f"decoded value {value} is out of range for a UUID (must be < 2**128)"
            )
        return encoded

    def validate_string(self, strval):
        """Validates a string against this field's config.

        Raises `MalformedSpicyIdError` on any error.
        """
        self._validate_string_internal(strval)

    def _validate_spicy_id(self, value):
        try:
            self._validate_string_internal(value)
        except MalformedSpicyIdError as e:
            raise ValidationError(str(e), code="invalid")

    @cached_property
    def validators(self):
        def spicy_id_validator(value):
            if isinstance(value, str):
                self._validate_spicy_id(value)

        return [spicy_id_validator]

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if isinstance(value, str):
            value = uuid.UUID(value)
        return self._to_string(value)

    def _to_uuid(self, value):
        """Converts a value to a uuid.UUID, accepting spicy strings, UUID objects, and raw strings."""
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            if self.re.match(value):
                encoded = self._validate_string_internal(value)
                int_value = self.codec.decode(encoded)
                return uuid.UUID(int=int_value)
            return uuid.UUID(value)
        return None

    def get_prep_value(self, value):
        if not value:
            return None
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            try:
                return self._to_uuid(value)
            except (MalformedSpicyIdError, ValueError) as e:
                raise ProgrammingError(f"the value {repr(value)} is not valid: {e}")
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            try:
                value = self._to_uuid(value)
            except (MalformedSpicyIdError, ValueError):
                value = uuid.UUID(value) if isinstance(value, str) else value
        if connection.features.has_native_uuid_field:
            return value
        return value.hex

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, str) and self.re.match(value):
            self._validate_spicy_id(value)  # also enforces the 128-bit range
            return value
        if isinstance(value, uuid.UUID):
            return self._to_string(value)
        if isinstance(value, str):
            try:
                return self._to_string(uuid.UUID(value))
            except (AttributeError, ValueError):
                raise ValidationError(
                    f"The value {repr(value)} is not valid for this field",
                    code="invalid",
                )
        raise ValidationError(
            f"The value {repr(value)} is not valid for this field",
            code="invalid",
        )

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["prefix"] = self.prefix
        kwargs["sep"] = self.sep
        kwargs["encoding"] = self.encoding
        if "default" in kwargs and kwargs["default"] is uuid.uuid4:
            del kwargs["default"]
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)

        def spicy_uuid_post_save(sender, instance, created, raw, **kwargs):
            if raw:
                return
            nonlocal name
            val = getattr(instance, name)
            if isinstance(val, uuid.UUID):
                setattr(instance, name, self._to_string(val))

        post_save.connect(spicy_uuid_post_save, sender=cls, weak=False)

    def pre_save(self, model_instance, add):
        value = getattr(model_instance, self.attname)
        if isinstance(value, str) and self.re.match(value):
            # Return the decoded UUID for the query without mutating the
            # instance, so a failed save doesn't leave a raw UUID on it.
            return self._to_uuid(value)
        return super().pre_save(model_instance, add)

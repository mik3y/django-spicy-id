import re
import secrets
import time
import uuid
import warnings

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.db.utils import ProgrammingError
from django.utils.functional import cached_property

from django_spicy_id.errors import MalformedSpicyIdError

from . import baseconv

# Encoding strategies which may be selected with the `encoding=` field parameter.
ENCODING_HEX = "hex"
ENCODING_BASE_32 = "b32"
ENCODING_BASE_58 = "b58"
ENCODING_BASE_62 = "b62"

# Maps encoding strategy to its encoder/decoder.
CODECS_BY_ENCODING = {
    ENCODING_HEX: baseconv.base16,
    ENCODING_BASE_32: baseconv.base32_crockford,
    ENCODING_BASE_58: baseconv.base58,
    ENCODING_BASE_62: baseconv.base62,
}

# Validates acceptable values for the `prefix=` field parameter.
LEGAL_PREFIX_RE = re.compile("^[a-zA-Z][0-9a-zA-Z]*$")

# TypeID (https://github.com/jetify-com/typeid) constraints. The suffix is always
# exactly 26 base32 characters, and the prefix is lowercase snake_case ascii of at
# most 63 characters that starts and ends with a letter (or is empty).
TYPEID_SUFFIX_LEN = 26
TYPEID_MAX_PREFIX_LEN = 63
LEGAL_TYPEID_PREFIX_RE = re.compile(r"^([a-z]([a-z_]{0,61}[a-z])?)?$")


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


def uuid7():
    """Returns a new UUIDv7 (time-ordered), per RFC 9562.

    Delegates to the stdlib `uuid.uuid7` when available (Python 3.14+); otherwise
    builds one from a millisecond timestamp plus random bits. Used as the default
    value generator for `TypeIDField`, since the TypeID spec requires
    generated ids to decode to a valid UUIDv7.
    """
    if hasattr(uuid, "uuid7"):
        return uuid.uuid7()

    unix_ms = time.time_ns() // 1_000_000
    value = (unix_ms & 0xFFFFFFFFFFFF) << 80  # 48-bit timestamp
    value |= 0x7 << 76  # 4-bit version
    value |= secrets.randbits(12) << 64  # 12 bits rand_a
    value |= 0b10 << 62  # 2-bit variant
    value |= secrets.randbits(62)  # 62 bits rand_b
    return uuid.UUID(int=value)


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
        if not m:
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
    """A "spicy" typed ID backed by a 64-bit `BigAutoField` column.

    Behaves like a normal `BigAutoField`, the stored value is a database-generated
    integer, but it is displayed and queried as a prefixed string such as
    `user_8M0kX`.

    Arguments:
        prefix: The type prefix shown on every id, e.g. `user`. Required.
        sep: The separator between the prefix and the encoded value. Defaults to `_`.
        encoding: How the integer value is encoded. One of `ENCODING_BASE_62`
            (default), `ENCODING_BASE_58`, `ENCODING_BASE_32`, or `ENCODING_HEX`.
        pad: If `True`, zero-pad the encoded value so all ids are the same length.
            Defaults to `False`.
        randomize: If `True`, assign a random (rather than sequential) value on
            insert, using `secrets`. Defaults to `False`.
    """

    NUM_BITS = 64


class SpicyAutoField(BaseSpicyAutoField, models.AutoField):
    """A "spicy" typed ID backed by a 32-bit `AutoField` column.

    Takes the same arguments as `SpicyBigAutoField`.
    """

    NUM_BITS = 32


class SpicySmallAutoField(BaseSpicyAutoField, models.SmallAutoField):
    """A "spicy" typed ID backed by a 16-bit `SmallAutoField` column.

    Takes the same arguments as `SpicyBigAutoField`.

    **Deprecated:** scheduled for removal in v2.0.0. Use `SpicyAutoField` instead.
    """

    NUM_BITS = 16

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "SpicySmallAutoField is deprecated and will be removed in v2.0.0; "
            "use SpicyAutoField instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class _SpicyIdFormField(forms.CharField):
    """Form field for the UUID-backed spicy id fields.

    Accepts anything the model field's `to_python` accepts (spicy id strings,
    raw UUID strings) and normalizes the value to the spicy string form.
    """

    def __init__(self, *, model_field, **kwargs):
        self.model_field = model_field
        super().__init__(**kwargs)

    def prepare_value(self, value):
        # An unsaved instance may still hold its raw UUID default value;
        # display it in the field's canonical string form.
        if isinstance(value, uuid.UUID):
            return self.model_field._to_string(value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return self.model_field.to_python(value)


class SpicyUUIDField(models.UUIDField):
    """A "spicy" typed ID backed by a 128-bit `UUIDField` column.

    **Deprecated:** scheduled for removal in v2.0.0. Use `TypeIDField` instead.

    Unlike the auto fields, the value is not database-generated; a random
    `uuid.uuid4` is assigned to new rows by default. It is displayed and queried
    as a prefixed, encoded string.

    Arguments:
        prefix: The type prefix shown on every id, e.g. `user`. Required.
        sep: The separator between the prefix and the encoded value. Defaults to `_`.
        encoding: How the UUID is encoded. One of `ENCODING_BASE_62` (default),
            `ENCODING_BASE_58`, `ENCODING_BASE_32`, or `ENCODING_HEX`.
    """

    def __init__(
        self,
        prefix,
        sep="_",
        encoding=ENCODING_BASE_62,
        *args,
        **kwargs,
    ):
        # Guard on the exact type so subclasses (e.g. TypeIDField) don't inherit
        # this deprecation. TypeIDField bypasses this __init__ anyway, but this
        # keeps the warning correct for any future subclass.
        if type(self) is SpicyUUIDField:
            warnings.warn(
                "SpicyUUIDField is deprecated and will be removed in v2.0.0; "
                "use TypeIDField instead.",
                DeprecationWarning,
                stacklevel=2,
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

    def formfield(self, **kwargs):
        # `models.UUIDField` would default this to `forms.UUIDField`, which
        # rejects the prefixed strings this field renders. Use a CharField-based
        # form field that accepts and normalizes spicy id strings instead.
        return super().formfield(**{"form_class": _SpicyIdFormField, "model_field": self, **kwargs})


class TypeIDField(SpicyUUIDField):
    """A field implementing the TypeID spec, backed by a `UUIDField` column.

    TypeIDs (https://github.com/jetify-com/typeid) are UUIDv7 values rendered in
    Crockford base32 with a lowercase snake_case type prefix, e.g.
    `user_01h455vb4pex5vsknk084sn02q`. This field produces and accepts exactly
    that format while storing the value as a native UUID.

    The `encoding` (base32), separator (`_`), and fixed 26-character zero padding
    are all mandated by the spec and are not configurable. New rows default to a
    freshly generated UUIDv7 (see `uuid7`).

    Arguments:
        prefix: The type prefix, following the TypeID rules: lowercase ascii
            `[a-z_]`, at most 63 characters, starting and ending with a letter.
            May be empty, in which case the separator is omitted.
    """

    def __init__(self, prefix="", *args, **kwargs):
        if not isinstance(prefix, str):
            raise ImproperlyConfigured("prefix must be a string")
        if len(prefix) > TYPEID_MAX_PREFIX_LEN:
            raise ImproperlyConfigured(
                f"prefix: must be at most {TYPEID_MAX_PREFIX_LEN} characters"
            )
        if not LEGAL_TYPEID_PREFIX_RE.match(prefix):
            raise ImproperlyConfigured(
                "prefix: TypeID prefixes must be empty or lowercase ascii [a-z_], "
                "starting and ending with a letter"
            )
        # `sep` and `encoding` are dictated by the spec; reject attempts to set them
        # so a misconfiguration fails loudly rather than silently being ignored.
        for fixed in ("sep", "encoding"):
            if fixed in kwargs:
                raise ImproperlyConfigured(f"`{fixed}` is not configurable on a TypeID field")

        self.prefix = prefix
        self.sep = "_"
        self.encoding = ENCODING_BASE_32
        self.codec = CODECS_BY_ENCODING[self.encoding]
        self.max_characters = TYPEID_SUFFIX_LEN

        # The separator is omitted entirely when the prefix is empty.
        preamble = f"{self.prefix}{self.sep}" if self.prefix else ""
        self.re = get_regex(preamble, self.codec, True, TYPEID_SUFFIX_LEN)
        self.re_pattern = self.re.pattern[1:-1]

        kwargs.setdefault("default", uuid7)
        # Bypass SpicyUUIDField.__init__, whose prefix/encoding rules differ; the
        # setup above is the TypeID-specific equivalent.
        models.UUIDField.__init__(self, *args, **kwargs)

    def _to_string(self, uid):
        if not isinstance(uid, uuid.UUID):
            uid = uuid.UUID(uid) if isinstance(uid, str) else uuid.UUID(int=uid)
        encoded = self.codec.encode(uid.int).rjust(TYPEID_SUFFIX_LEN, self.codec.digits[0])
        if not self.prefix:
            return encoded
        return f"{self.prefix}{self.sep}{encoded}"

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # `sep` and `encoding` are implied by the field type and rejected by
        # __init__, so they must not be emitted into migrations.
        kwargs.pop("sep", None)
        kwargs.pop("encoding", None)
        if "default" in kwargs and kwargs["default"] is uuid7:
            del kwargs["default"]
        return name, path, args, kwargs

"""Tests for TypeIDField, including the official TypeID spec conformance vectors.

The `VALID_VECTORS` and `INVALID_*` constants are taken verbatim from the TypeID
spec's `valid.yml` / `invalid.yml` conformance suites:
https://github.com/jetify-com/typeid/tree/main/spec
"""

import uuid

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.utils import ProgrammingError
from django.forms import modelform_factory
from django.test import TestCase

from django_spicy_id import MalformedSpicyIdError, TypeIDField
from django_spicy_id.fields import uuid7
from django_spicy_id.tests import models

# (name, typeid, prefix, uuid) tuples from the spec's valid.yml.
VALID_VECTORS = [
    ("nil", "00000000000000000000000000", "", "00000000-0000-0000-0000-000000000000"),
    ("one", "00000000000000000000000001", "", "00000000-0000-0000-0000-000000000001"),
    ("ten", "0000000000000000000000000a", "", "00000000-0000-0000-0000-00000000000a"),
    ("sixteen", "0000000000000000000000000g", "", "00000000-0000-0000-0000-000000000010"),
    ("thirty-two", "00000000000000000000000010", "", "00000000-0000-0000-0000-000000000020"),
    ("max-valid", "7zzzzzzzzzzzzzzzzzzzzzzzzz", "", "ffffffff-ffff-ffff-ffff-ffffffffffff"),
    (
        "valid-alphabet",
        "prefix_0123456789abcdefghjkmnpqrs",
        "prefix",
        "0110c853-1d09-52d8-d73e-1194e95b5f19",
    ),
    (
        "valid-uuidv7",
        "prefix_01h455vb4pex5vsknk084sn02q",
        "prefix",
        "01890a5d-ac96-774b-bcce-b302099a8057",
    ),
    (
        "prefix-underscore",
        "pre_fix_00000000000000000000000000",
        "pre_fix",
        "00000000-0000-0000-0000-000000000000",
    ),
]

# Prefixes that must be rejected at field-construction time, from invalid.yml.
INVALID_PREFIXES = [
    "PREFIX",  # uppercase
    "12345",  # numeric
    "pre.fix",  # symbol
    "préfix",  # non-ascii
    "  prefix",  # spaces
    "a" * 64,  # too long (max 63)
    "_prefix",  # leading underscore
    "prefix_",  # trailing underscore
]

# Suffixes (paired with prefix "prefix") that must fail to parse, from invalid.yml.
INVALID_SUFFIXES = [
    "1234567890123456789012345",  # 25 chars, too short
    "123456789012345678901234567",  # 27 chars, too long
    "1234567890123456789012345 ",  # trailing space
    "0123456789ABCDEFGHJKMNPQRS",  # uppercase
    "123456789-123456789-123456",  # hyphens
    "ooooooiiiiiiuuuuuuulllllll",  # letters outside the alphabet
    "i23456789ol23456789oi23456",  # ambiguous crockford letters
    "8zzzzzzzzzzzzzzzzzzzzzzzzz",  # overflows 128 bits (first char > 7)
]


class TestTypeIDFieldConfiguration(TestCase):
    def test_rejects_bad_prefixes(self):
        for prefix in INVALID_PREFIXES:
            with self.assertRaises(ImproperlyConfigured, msg=f"prefix={prefix!r}"):
                TypeIDField(prefix=prefix)

    def test_accepts_valid_prefixes(self):
        for prefix in ("", "a", "user", "pre_fix", "a_b_c", "my__type", "a" * 63):
            TypeIDField(prefix=prefix)  # must not raise

    def test_sep_and_encoding_not_configurable(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "`sep` is not configurable"):
            TypeIDField(prefix="user", sep="-")
        with self.assertRaisesMessage(ImproperlyConfigured, "`encoding` is not configurable"):
            TypeIDField(prefix="user", encoding="hex")

    def test_default_is_uuidv7(self):
        field = TypeIDField(prefix="user")
        generated = field.get_default()
        self.assertIsInstance(generated, uuid.UUID)
        self.assertEqual(7, generated.version)

    def test_deconstruct(self):
        field = TypeIDField(prefix="user")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["prefix"], "user")
        # sep/encoding/default are all implied and must not leak into migrations.
        self.assertNotIn("sep", kwargs)
        self.assertNotIn("encoding", kwargs)
        self.assertNotIn("default", kwargs)


class TestTypeIDConformance(TestCase):
    def test_valid_vectors_roundtrip(self):
        for name, typeid, prefix, uuid_str in VALID_VECTORS:
            field = TypeIDField(prefix=prefix)
            uid = uuid.UUID(uuid_str)
            # Encoding the UUID must produce exactly the spec's string...
            self.assertEqual(typeid, field._to_string(uid), msg=name)
            # ...and parsing the string must recover the original UUID.
            self.assertEqual(uid, field._to_uuid(typeid), msg=name)
            # The string must also validate cleanly.
            field.validate_string(typeid)

    def test_invalid_suffixes_rejected(self):
        field = TypeIDField(prefix="prefix")
        for suffix in INVALID_SUFFIXES:
            with self.assertRaises(MalformedSpicyIdError, msg=repr(suffix)):
                field.validate_string(f"prefix_{suffix}")

    def test_empty_prefix_rejects_stray_separator(self):
        field = TypeIDField(prefix="")
        for bad in ("_00000000000000000000000000", "_", ""):
            with self.assertRaises(MalformedSpicyIdError, msg=repr(bad)):
                field.validate_string(bad)

    def test_nonempty_prefix_rejects_empty_suffix(self):
        field = TypeIDField(prefix="prefix")
        with self.assertRaises(MalformedSpicyIdError):
            field.validate_string("prefix_")


class TestTypeIDFieldModel(TestCase):
    # prefix_01h455vb4pex5vsknk084sn02q from the spec's valid.yml.
    TEST_UUID = uuid.UUID("01890a5d-ac96-774b-bcce-b302099a8057")
    TEST_TYPEID = "prefix_01h455vb4pex5vsknk084sn02q"

    def test_create_by_uuid(self):
        obj = models.TypeIDModel.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_TYPEID, obj.id)

    def test_create_by_string(self):
        obj = models.TypeIDModel.objects.create(id=self.TEST_TYPEID)
        self.assertEqual(self.TEST_TYPEID, obj.id)

    def test_roundtrip_fetch_by_string(self):
        models.TypeIDModel.objects.create(id=self.TEST_UUID)
        retrieved = models.TypeIDModel.objects.filter(pk=self.TEST_TYPEID).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(self.TEST_TYPEID, retrieved.id)

    def test_default_generates_valid_typeid(self):
        obj = models.TypeIDModel.objects.create()
        self.assertTrue(obj.id.startswith("prefix_"))
        self.assertEqual(len("prefix_") + 26, len(obj.id))
        # The generated suffix must decode back to a v7 UUID.
        field = models.TypeIDModel._meta.get_field("id")
        self.assertEqual(7, field._to_uuid(obj.id).version)

    def test_invalid_string_rejected(self):
        with self.assertRaises(ProgrammingError):
            models.TypeIDModel.objects.filter(pk="wrong_abc").first()

    def test_save_with_out_of_range_string_raises_programming_error(self):
        """An out-of-range suffix fails save() with the library's error type."""
        obj = models.TypeIDModel(id="prefix_8zzzzzzzzzzzzzzzzzzzzzzzzz")
        with self.assertRaises(ProgrammingError):
            obj.save()

    def test_full_clean_rejects_invalid(self):
        obj = models.TypeIDModel.objects.create(id=self.TEST_UUID)
        obj.id = "prefix_0123456789ABCDEFGHJKMNPQRS"  # uppercase suffix
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_empty_prefix_model(self):
        uid = uuid.UUID("00000000-0000-0000-0000-000000000010")
        obj = models.TypeIDModel_NoPrefix.objects.create(id=uid)
        self.assertEqual("0000000000000000000000000g", obj.id)
        retrieved = models.TypeIDModel_NoPrefix.objects.filter(pk=obj.id).first()
        self.assertEqual(obj.id, retrieved.id)

    def test_modelform_roundtrip(self):
        """A ModelForm must accept and save the field's own string format."""
        form_class = modelform_factory(models.TypeIDModel, fields=["id"])
        form = form_class(data={"id": self.TEST_TYPEID})
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(self.TEST_TYPEID, obj.id)

    def test_modelform_rejects_invalid_typeid(self):
        form_class = modelform_factory(models.TypeIDModel, fields=["id"])
        form = form_class(data={"id": "prefix_0123456789ABCDEFGHJKMNPQRS"})
        self.assertFalse(form.is_valid())
        self.assertIn("id", form.errors)


class TestUUID7(TestCase):
    def test_uuid7_is_version_7(self):
        u = uuid7()
        self.assertIsInstance(u, uuid.UUID)
        self.assertEqual(7, u.version)
        self.assertEqual(uuid.RFC_4122, u.variant)

    def test_uuid7_values_differ(self):
        self.assertNotEqual(uuid7(), uuid7())

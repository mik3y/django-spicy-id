import uuid
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.utils import ProgrammingError
from django.test import TestCase

from django_spicy_id import SpicyAutoField, SpicyUUIDField
from django_spicy_id.fields import LEGAL_PREFIX_RE
from django_spicy_id.tests import models


class TestFields(TestCase):
    def test_prefix_re(self):
        legal_prefixes = (
            "e",
            "ex",
            "ExampleThatsReallyLong",
        )
        for p in legal_prefixes:
            self.assertIsNotNone(LEGAL_PREFIX_RE.match(p))

        illegal_prefixes = (
            "",
            "🆒",
            "9gag",
        )
        for p in illegal_prefixes:
            self.assertIsNone(LEGAL_PREFIX_RE.match(p))

    def test_field_configuration(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "unknown encoding"):
            SpicyAutoField(prefix="yo", encoding="doop")

        with self.assertRaisesMessage(
            ImproperlyConfigured, "prefix: only ascii numbers and letters allowed"
        ):
            SpicyAutoField(prefix="")

        with self.assertRaisesMessage(
            ImproperlyConfigured, "prefix: only ascii numbers and letters allowed"
        ):
            SpicyAutoField(prefix="yo🆒dude")

        with self.assertRaisesMessage(ImproperlyConfigured, "must start with a letter"):
            SpicyAutoField(prefix="976love")

        with self.assertRaisesMessage(ImproperlyConfigured, "prefix must be a string"):
            SpicyAutoField(prefix=123)

        with self.assertRaisesMessage(ImproperlyConfigured, "sep must be a string"):
            SpicyAutoField(prefix="ex", sep=123)

        with self.assertRaisesMessage(ImproperlyConfigured, "sep must be ascii"):
            SpicyAutoField(prefix="ex", sep="frozen🍌")

        with self.assertRaisesMessage(
            ImproperlyConfigured, "cannot provide both `randomize` and `default`"
        ):
            SpicyAutoField(prefix="ex", default=123, randomize=True)

    def test_model_with_defaults(self):
        model = models.Model_WithDefaults

        obj1 = model.objects.create()
        self.assertEqual("ex_1", obj1.id)
        obj2 = model.objects.create()
        self.assertEqual("ex_2", obj2.id)
        for i in range(7):
            model.objects.create()
        obj10 = model.objects.create()
        self.assertEqual("ex_A", obj10.id)

        custom = model.objects.create(id=123456789)
        self.assertEqual("ex_8M0kX", custom.id)

        # When padding is disabled, it's an error to use padding characters.
        self.assertTrue(model.objects.filter(id="ex_8M0kX").first())
        with self.assertRaises(ProgrammingError):
            model.objects.filter(id="ex_0008M0kX").first()

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_AzL8n0Y58m7", boundary.id)

    def test_hex_model_with_defaults(self):
        model = models.HexModel_WithDefaults

        obj1 = model.objects.create()
        self.assertEqual("ex_1", obj1.id)
        obj2 = model.objects.create()
        self.assertEqual("ex_2", obj2.id)
        for i in range(7):
            model.objects.create()
        obj10 = model.objects.create()
        self.assertEqual("ex_a", obj10.id)

        custom = model.objects.create(id=123456789)
        self.assertEqual("ex_75bcd15", custom.id)

        # Using uppercase hex characters (i.e. supporting multiple legal
        # representations of the same value) is not allowed.
        with self.assertRaises(ProgrammingError):
            model.objects.filter(id="ex_75BCD15").first()

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_7fffffffffffffff", boundary.id)

    def test_base58_model_with_padding(self):
        model = models.Base58Model_WithPadding

        o = model.objects.create()
        self.assertEqual("ex_11111111112", o.id)
        custom = model.objects.create(id=123456789)
        self.assertEqual("ex_111111BukQL", custom.id)

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_NQm6nKp8qFC", boundary.id)

    def test_base62_model_with_padding(self):
        model = models.Base62Model_WithPadding

        o = model.objects.create()
        self.assertEqual("ex_00000000001", o.id)
        custom = model.objects.create(id=123456789)
        self.assertEqual("ex_0000008M0kX", custom.id)

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_AzL8n0Y58m7", boundary.id)

    def test_hex_model_with_padding(self):
        model = models.HexModel_WithPadding

        o = model.objects.create()
        self.assertEqual("ex_0000000000000001", o.id)
        custom = model.objects.create(id=123456789)
        self.assertEqual("ex_00000000075bcd15", custom.id)

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_7fffffffffffffff", boundary.id)

    @mock.patch("secrets.randbelow")
    def test_base62_model_with_randomize(self, mock_secrets_randbelow):
        model = models.Base62Model_WithRandomize

        mock_secrets_randbelow.return_value = 123456788
        o = model.objects.create()
        self.assertEqual("ex_8M0kX", o.id)
        mock_secrets_randbelow.assert_called_with(2**63 - 2)
        o = model.objects.create(id=7)
        self.assertEqual("ex_7", o.id)

    @mock.patch("secrets.randbelow")
    def test_hex_model_with_randomize(self, mock_secrets_randbelow):
        model = models.HexModel_WithRandomize

        mock_secrets_randbelow.return_value = 123456788
        o = model.objects.create()
        self.assertEqual("ex_75bcd15", o.id)
        mock_secrets_randbelow.assert_called_with(2**63 - 2)
        o = model.objects.create(id=7)
        self.assertEqual("ex_7", o.id)

    def test_base62_model_fetch_by_string(self):
        model = models.Base62Model_WithPadding

        o = model.objects.create(id=123456789)
        self.assertEqual("ex_0000008M0kX", o.id)

        retrieved = model.objects.filter(pk="ex_0000008M0kX").first()
        self.assertEqual(retrieved, o)

        # Exact padding characters are mandatory when configured on the field.
        with self.assertRaises(ProgrammingError):
            model.objects.filter(pk="ex_0008M0kX").first()
        self.assertEqual(retrieved, o)

    def test_hex_model_fetch_by_string(self):
        model = models.HexModel_WithPadding

        o = model.objects.create(id=123456789)
        self.assertEqual("ex_00000000075bcd15", o.id)

        retrieved = model.objects.filter(pk="ex_00000000075bcd15").first()
        self.assertEqual(retrieved, o)

        # Exact padding characters are mandatory when configured on the field.
        with self.assertRaises(ProgrammingError):
            model.objects.filter(pk="ex_0075bcd15").first()
        self.assertEqual(retrieved, o)

    def test_base62_model_create_by_string(self):
        model = models.Base62Model_WithPadding
        o = model.objects.create(id="ex_0000000007j")
        self.assertEqual("ex_0000000007j", o.id)

    def test_hex_model_create_by_string(self):
        model = models.HexModel_WithPadding
        o = model.objects.create(id="ex_0000000000000123")
        self.assertEqual("ex_0000000000000123", o.id)

        # Exact padding characters are mandatory when configured on the field.
        with self.assertRaises(ProgrammingError):
            model.objects.create(id="ex_000124")

    def test_base62_model_create_by_integer(self):
        model = models.HexModel_WithPadding
        o = model.objects.create(id=0x123)
        self.assertEqual("ex_0000000000000123", o.id)

    @mock.patch("secrets.randbelow")
    def test_randomize_sets_pk_to_a_string(self, mock_secrets_randbelow):
        """Ensures that when `randomize` is used, the value set is a string not a number."""
        model = models.SpicyAutoFieldModel_WithRandomize

        mock_secrets_randbelow.return_value = 1
        o = model()
        self.assertEqual("ex_2", o.id)
        self.assertTrue(o._state.adding)
        o.save()
        self.assertEqual("ex_2", o.id)
        self.assertFalse(o._state.adding)

    def test_full_clean_with_spicy_id(self):
        """Ensures full_clean() works on a model instance with a spicy id."""
        model = models.Model_WithDefaults
        obj = model.objects.create()
        self.assertEqual("ex_1", obj.id)
        obj.full_clean()

    @mock.patch("secrets.randbelow")
    def test_full_clean_with_randomized_spicy_id(self, mock_secrets_randbelow):
        """Ensures full_clean() works on a model with randomize=True."""
        model = models.Base62Model_WithRandomize
        mock_secrets_randbelow.return_value = 123456788
        obj = model.objects.create()
        self.assertEqual("ex_8M0kX", obj.id)
        obj.full_clean()

    def test_full_clean_rejects_invalid_spicy_id(self):
        """Ensures full_clean() catches an invalid spicy id string."""
        model = models.Model_WithDefaults
        obj = model.objects.create()
        obj.id = "wrong_prefix_123"
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_full_clean_validates_integer_value(self):
        """Ensures full_clean() applies integer range validators for int values."""
        model = models.Model_WithDefaults
        obj = model.objects.create()
        obj.id = 42
        obj.full_clean()  # valid integer should pass


class TestSpicyUUIDField(TestCase):
    TEST_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
    TEST_UUID_B62 = "uu_YLmNWW2NwaipfRR50HIPA"
    TEST_UUID_HEX = "uu_12345678123456781234567812345678"
    TEST_UUID_B58 = "uu_3FP9SaFPBg7Kw7fetjn6cF"

    def test_uuid_model_with_defaults(self):
        model = models.UUIDModel_WithDefaults

        obj = model.objects.create()
        self.assertTrue(obj.id.startswith("uu_"))
        self.assertIsInstance(obj.id, str)

    def test_uuid_model_create_by_uuid(self):
        model = models.UUIDModel_WithDefaults

        obj = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_B62, obj.id)

        obj.delete()
        obj2 = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_B62, obj2.id)

    def test_uuid_model_create_by_string(self):
        model = models.UUIDModel_WithDefaults

        obj = model.objects.create(id=self.TEST_UUID_B62)
        self.assertEqual(self.TEST_UUID_B62, obj.id)

    def test_uuid_model_roundtrip(self):
        model = models.UUIDModel_WithDefaults

        obj = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_B62, obj.id)

        retrieved = model.objects.filter(pk=self.TEST_UUID_B62).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(self.TEST_UUID_B62, retrieved.id)

    def test_hex_encoding(self):
        model = models.UUIDModel_Hex

        obj = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_HEX, obj.id)

    def test_base58_encoding(self):
        model = models.UUIDModel_Base58

        obj = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_B58, obj.id)

    def test_fetch_by_string(self):
        model = models.UUIDModel_WithDefaults

        model.objects.create(id=self.TEST_UUID)
        retrieved = model.objects.filter(pk=self.TEST_UUID_B62).first()
        self.assertEqual(self.TEST_UUID_B62, retrieved.id)

    def test_invalid_string_rejected(self):
        model = models.UUIDModel_WithDefaults
        with self.assertRaises(ProgrammingError):
            model.objects.filter(pk="wrong_abc").first()

    def test_full_clean(self):
        model = models.UUIDModel_WithDefaults
        obj = model.objects.create(id=self.TEST_UUID)
        self.assertEqual(self.TEST_UUID_B62, obj.id)
        obj.full_clean()

    def test_full_clean_rejects_invalid(self):
        model = models.UUIDModel_WithDefaults
        obj = model.objects.create(id=self.TEST_UUID)
        obj.id = "wrong_prefix_123"
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_deconstruct(self):
        field = SpicyUUIDField(prefix="uu", sep="-", encoding="hex")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["prefix"], "uu")
        self.assertEqual(kwargs["sep"], "-")
        self.assertEqual(kwargs["encoding"], "hex")

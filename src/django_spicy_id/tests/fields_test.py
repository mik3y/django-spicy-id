import uuid
import warnings
from unittest import mock

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection
from django.db.utils import ProgrammingError
from django.test import TestCase, TransactionTestCase

from django_spicy_id import (
    MalformedSpicyIdError,
    SpicyAutoField,
    SpicySmallAutoField,
    SpicyUUIDField,
    TypeIDField,
)
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

    def test_rejects_out_of_range_string(self):
        """A regex-valid but numerically over-range id is rejected before the DB."""
        field = SpicyAutoField(prefix="ex")  # 32-bit, base62 -> max 6 characters
        over_range = "ex_zzzzzz"  # 6 chars, but decodes above 2**31 - 1
        with self.assertRaises(MalformedSpicyIdError):
            field.validate_string(over_range)
        with self.assertRaises(ProgrammingError):
            field.get_prep_value(over_range)
        with self.assertRaises(ValidationError):
            field.to_python(over_range)

    def test_padded_zero_is_accepted(self):
        """A padded field accepts the all-zero id; 0 is a legal integer value."""
        field = SpicyAutoField(prefix="ex", pad=True)
        zero = "ex_" + "0" * field.max_characters
        field.validate_string(zero)  # must not raise
        self.assertEqual(0, field.get_prep_value(zero))

    def test_unpadded_zero_roundtrips(self):
        """The zero id renders as a single pad character and must parse back."""
        field = SpicyAutoField(prefix="ex")
        self.assertEqual("ex_0", field._to_string(0))
        field.validate_string("ex_0")  # must not raise
        self.assertEqual(0, field.get_prep_value("ex_0"))
        # base58's pad character is "1", not "0".
        b58_field = SpicyAutoField(prefix="ex", encoding="b58")
        self.assertEqual("ex_1", b58_field._to_string(0))
        self.assertEqual(0, b58_field.get_prep_value("ex_1"))

    def test_unpadded_ids_still_reject_leading_pad_chars(self):
        field = SpicyAutoField(prefix="ex")
        for bad in ("ex_00", "ex_01", "ex_0A"):
            with self.assertRaises(MalformedSpicyIdError, msg=repr(bad)):
                field.validate_string(bad)

    @mock.patch("secrets.randbelow")
    def test_base62_model_with_randomize(self, mock_secrets_randbelow):
        model = models.Base62Model_WithRandomize

        mock_secrets_randbelow.return_value = 123456788
        o = model.objects.create()
        self.assertEqual("ex_8M0kX", o.id)
        mock_secrets_randbelow.assert_called_with(2**63 - 1)
        o = model.objects.create(id=7)
        self.assertEqual("ex_7", o.id)

    @mock.patch("secrets.randbelow")
    def test_hex_model_with_randomize(self, mock_secrets_randbelow):
        model = models.HexModel_WithRandomize

        mock_secrets_randbelow.return_value = 123456788
        o = model.objects.create()
        self.assertEqual("ex_75bcd15", o.id)
        mock_secrets_randbelow.assert_called_with(2**63 - 1)
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

    def test_user_supplied_validators_run_for_strings(self):
        seen = []
        field = SpicyAutoField(prefix="ex", validators=[seen.append])
        field.run_validators("ex_8M0kX")
        self.assertEqual(["ex_8M0kX"], seen)

    def test_user_supplied_validators_run_for_integers(self):
        seen = []
        field = SpicyAutoField(prefix="ex", validators=[seen.append])
        field.run_validators(42)
        self.assertEqual([42], seen)

    def test_integer_range_validators_still_apply(self):
        min_value, max_value = connection.ops.integer_field_range("AutoField")
        if max_value is None:
            self.skipTest("backend does not enforce integer ranges")
        field = SpicyAutoField(prefix="ex", validators=[lambda value: None])
        with self.assertRaises(ValidationError):
            field.run_validators(max_value + 1)

    def test_full_clean_runs_user_supplied_validators(self):
        obj = models.Model_WithCustomValidator.objects.create(id=13)
        self.assertEqual("ex_D", obj.id)
        with self.assertRaisesMessage(ValidationError, "thirteen is unlucky"):
            obj.full_clean()


class TestFieldsWithFreshCounters(TransactionTestCase):
    """Tests that assert absolute auto-increment values (e.g. "the first row is ex_1").

    On MySQL and PostgreSQL, auto-increment counters are not rolled back with
    the per-test transaction that django.test.TestCase uses, so counter state
    leaks between tests. `reset_sequences` restores each table's counter before
    every test in this class.
    """

    reset_sequences = True

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

    def test_full_clean_with_spicy_id(self):
        """Ensures full_clean() works on a model instance with a spicy id."""
        model = models.Model_WithDefaults
        obj = model.objects.create()
        self.assertEqual("ex_1", obj.id)
        obj.full_clean()


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

    def test_rejects_out_of_range_string(self):
        """A regex-valid string that decodes above the 128-bit range is rejected."""
        field = SpicyUUIDField(prefix="uu")  # base62 -> max 22 characters
        over_range = "uu_" + "z" * 22  # decodes above 2**128
        with self.assertRaises(MalformedSpicyIdError):
            field.validate_string(over_range)
        with self.assertRaises(ProgrammingError):
            field.get_prep_value(over_range)
        with self.assertRaises(ValidationError):
            field.to_python(over_range)

    def test_deconstruct(self):
        field = SpicyUUIDField(prefix="uu", sep="-", encoding="hex")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["prefix"], "uu")
        self.assertEqual(kwargs["sep"], "-")
        self.assertEqual(kwargs["encoding"], "hex")

    def test_formfield_accepts_spicy_strings(self):
        """The form field must accept the strings the model field renders."""
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        form_field = field.formfield()
        self.assertNotIsInstance(form_field, forms.UUIDField)
        self.assertEqual(self.TEST_UUID_B62, form_field.clean(self.TEST_UUID_B62))

    def test_formfield_normalizes_raw_uuid_strings(self):
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        form_field = field.formfield()
        self.assertEqual(self.TEST_UUID_B62, form_field.clean(str(self.TEST_UUID)))

    def test_formfield_rejects_invalid_strings(self):
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        form_field = field.formfield()
        for bad in ("wrong_prefix_123", "uu_!!!!", "uu_" + "z" * 22):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                form_field.clean(bad)

    def test_formfield_displays_uuid_as_spicy_string(self):
        """Unsaved instances hold a raw UUID default; it must display as a spicy id."""
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        form_field = field.formfield()
        self.assertEqual(self.TEST_UUID_B62, form_field.prepare_value(self.TEST_UUID))

    def test_user_supplied_validators_run(self):
        seen = []
        field = SpicyUUIDField(prefix="uu", validators=[seen.append])
        field.run_validators(self.TEST_UUID_B62)
        self.assertEqual([self.TEST_UUID_B62], seen)

    def test_get_db_prep_value_accepts_supported_values(self):
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        expected = (
            self.TEST_UUID if connection.features.has_native_uuid_field else self.TEST_UUID.hex
        )
        for value in (self.TEST_UUID, self.TEST_UUID_B62, str(self.TEST_UUID)):
            self.assertEqual(expected, field.get_db_prep_value(value, connection), msg=repr(value))

    def test_get_db_prep_value_rejects_unsupported_types(self):
        """Unsupported types must raise, not be silently written as NULL."""
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        for bad in (12345, 1.5, object()):
            with self.assertRaises(ProgrammingError, msg=repr(bad)):
                field.get_db_prep_value(bad, connection)

    def test_get_db_prep_value_rejects_invalid_strings(self):
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        for bad in ("uu_" + "z" * 22, "not-a-uuid", ""):
            with self.assertRaises(ProgrammingError, msg=repr(bad)):
                field.get_db_prep_value(bad, connection)

    def test_nil_uuid_roundtrips(self):
        """The nil UUID renders as `uu_0` and must parse back."""
        field = models.UUIDModel_WithDefaults._meta.get_field("id")
        nil = uuid.UUID(int=0)
        rendered = field._to_string(nil)
        self.assertEqual("uu_0", rendered)
        field.validate_string(rendered)  # must not raise
        self.assertEqual(nil, field.get_prep_value(rendered))

        obj = models.UUIDModel_WithDefaults.objects.create(id=nil)
        self.assertEqual("uu_0", obj.id)
        retrieved = models.UUIDModel_WithDefaults.objects.filter(pk="uu_0").first()
        self.assertEqual(obj, retrieved)


class TestDeprecations(TestCase):
    def test_small_auto_field_is_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning, "use SpicyAutoField instead"):
            SpicySmallAutoField(prefix="ex")

    def test_uuid_field_is_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning, "use TypeIDField instead"):
            SpicyUUIDField(prefix="uu")

    def test_typeid_field_does_not_warn(self):
        """TypeIDField subclasses the deprecated SpicyUUIDField but is not itself deprecated."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            TypeIDField(prefix="user")  # must not raise

    def test_undeprecated_fields_do_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            SpicyAutoField(prefix="ex")  # must not raise

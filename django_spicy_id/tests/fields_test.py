from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db.utils import ProgrammingError
from django.test import TestCase

from django_spicy_id import MalformedSpicyIdError, SpicyAutoField
from django_spicy_id.tests import models


class TestFields(TestCase):
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

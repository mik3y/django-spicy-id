from unittest import mock

from django.test import TestCase

from django_spicy_id.fields import SpicyBigAutoField
from django_spicy_id.tests import models


class TestFields(TestCase):
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

        boundary = model.objects.create(id=2**63 - 1)
        self.assertEqual("ex_7fffffffffffffff", boundary.id)

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

    @mock.patch("random.randrange")
    def test_base62_model_with_randomize(self, mock_randrange):
        model = models.Base62Model_WithRandomize

        mock_randrange.return_value = 123456789
        o = model.objects.create()
        self.assertEqual("ex_8M0kX", o.id)
        mock_randrange.assert_called_with(1, 2**63 - 1)
        o = model.objects.create(id=7)
        self.assertEqual("ex_7", o.id)

    @mock.patch("random.randrange")
    def test_hex_model_with_randomize(self, mock_randrange):
        model = models.HexModel_WithRandomize

        mock_randrange.return_value = 123456789
        o = model.objects.create()
        self.assertEqual("ex_75bcd15", o.id)
        mock_randrange.assert_called_with(1, 2**63 - 1)
        o = model.objects.create(id=7)
        self.assertEqual("ex_7", o.id)

    def test_base62_model_fetch_by_string(self):
        model = models.Base62Model_WithPadding

        o = model.objects.create(id=123456789)
        self.assertEqual("ex_0000008M0kX", o.id)

        retrieved = model.objects.filter(pk="ex_0000008M0kX").first()
        self.assertEqual(retrieved, o)

        # Padding is ignored when fetched.
        # TODO(mikey): I do not like this behavior and we should make it an error,
        # since it means many different strings can resolve to the same object.
        retrieved = model.objects.filter(pk="ex_0008M0kX").first()
        self.assertEqual(retrieved, o)

    def test_hex_model_fetch_by_string(self):
        model = models.HexModel_WithPadding

        o = model.objects.create(id=123456789)
        self.assertEqual("ex_00000000075bcd15", o.id)

        retrieved = model.objects.filter(pk="ex_00000000075bcd15").first()
        self.assertEqual(retrieved, o)

        # Padding is ignored when fetched.
        # TODO(mikey): I do not like this behavior and we should make it an error,
        # since it means many different strings can resolve to the same object.
        retrieved = model.objects.filter(pk="ex_0075bcd15").first()
        self.assertEqual(retrieved, o)

    def test_base62_model_create_by_string(self):
        model = models.Base62Model_WithPadding
        o = model.objects.create(id="ex_7j")
        self.assertEqual("ex_0000000007j", o.id)

    def test_base62_model_create_by_string(self):
        model = models.HexModel_WithPadding
        o = model.objects.create(id="ex_000123")
        self.assertEqual("ex_0000000000000123", o.id)

"""Base conversion tests.

Adapted from `django.utils.baseconv` which bears the following license:

    Copyright (c) 2010 Guilherme Gondim. All rights reserved.
    Copyright (c) 2009 Simon Willison. All rights reserved.
    Copyright (c) 2002 Drew Perttula. All rights reserved.

    License:
      Python Software Foundation License version 2

    See the file "LICENSE" for terms & conditions for usage, and a DISCLAIMER OF
    ALL WARRANTIES.

    This Baseconv distribution contains no GNU General Public Licensed (GPLed)
    code so it may be used in proprietary projects just like prior ``baseconv``
    distributions.

    All trademarks referenced herein are property of their respective holders.
"""

from unittest import TestCase

from django_spicy_id.baseconv import BaseConverter, base16, base58, base62


class TestBaseConv(TestCase):
    def test_baseconv(self):
        nums = [-(10**10), 10**10, *range(-100, 100)]
        for converter in [base16, base58, base62]:
            for i in nums:
                self.assertEqual(i, converter.decode(converter.encode(i)))

    def test_base11(self):
        base11 = BaseConverter("0123456789-", sign="$")
        self.assertEqual(base11.encode(1234), "-22")
        self.assertEqual(base11.decode("-22"), 1234)
        self.assertEqual(base11.encode(-1234), "$-22")
        self.assertEqual(base11.decode("$-22"), -1234)

    def test_base20(self):
        base20 = BaseConverter("0123456789abcdefghij")
        self.assertEqual(base20.encode(1234), "31e")
        self.assertEqual(base20.decode("31e"), 1234)
        self.assertEqual(base20.encode(-1234), "-31e")
        self.assertEqual(base20.decode("-31e"), -1234)

    def test_base58(self):
        self.assertEqual(base58.encode(1234), "NH")
        self.assertEqual(base58.decode("NH"), 1234)
        self.assertEqual(base58.encode(-1234), "-NH")
        self.assertEqual(base58.decode("-NH"), -1234)

    def test_base62(self):
        self.assertEqual(base62.encode(1234), "Ju")
        self.assertEqual(base62.decode("Ju"), 1234)
        self.assertEqual(base62.encode(-1234), "-Ju")
        self.assertEqual(base62.decode("-Ju"), -1234)

    def test_base7(self):
        base7 = BaseConverter("cjdhel3", sign="g")
        self.assertEqual(base7.encode(1234), "hejd")
        self.assertEqual(base7.decode("hejd"), 1234)
        self.assertEqual(base7.encode(-1234), "ghejd")
        self.assertEqual(base7.decode("ghejd"), -1234)

    def test_exception(self):
        with self.assertRaises(ValueError):
            BaseConverter("abc", sign="a")
        self.assertIsInstance(BaseConverter("abc", sign="d"), BaseConverter)

    def test_repr(self):
        base7 = BaseConverter("cjdhel3", sign="g")
        self.assertEqual(repr(base7), "<BaseConverter: base7 (cjdhel3)>")

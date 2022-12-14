"""Base conversion utilities.

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

BASE16_ALPHABET = "0123456789abcdef"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


class BaseConverter:
    decimal_digits = "0123456789"

    def __init__(self, digits, sign="-"):
        self.sign = sign
        self.digits = digits
        if sign in self.digits:
            raise ValueError("Sign character found in converter base digits.")

    def __repr__(self):
        return "<%s: base%s (%s)>" % (
            self.__class__.__name__,
            len(self.digits),
            self.digits,
        )

    def encode(self, i):
        neg, value = self.convert(i, self.decimal_digits, self.digits, "-")
        if neg:
            return self.sign + value
        return value

    def decode(self, s):
        neg, value = self.convert(s, self.digits, self.decimal_digits, self.sign)
        if neg:
            value = "-" + value
        return int(value)

    def convert(self, number, from_digits, to_digits, sign):
        if str(number)[0] == sign:
            number = str(number)[1:]
            neg = 1
        else:
            neg = 0

        # make an integer out of the number
        x = 0
        for digit in str(number):
            x = x * len(from_digits) + from_digits.index(digit)

        # create the result in base 'len(to_digits)'
        if x == 0:
            res = to_digits[0]
        else:
            res = ""
            while x > 0:
                digit = x % len(to_digits)
                res = to_digits[digit] + res
                x = int(x // len(to_digits))
        return neg, res


base16 = BaseConverter(BASE16_ALPHABET)
base58 = BaseConverter(BASE58_ALPHABET)
base62 = BaseConverter(BASE62_ALPHABET)

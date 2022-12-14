from django.db import models

from django_spicy_id.fields import SpicyBigAutoField


class Model_WithDefaults(models.Model):
    """A model that uses a spicy field as its primary key."""

    id = SpicyBigAutoField("ex", primary_key=True)


class HexModel_WithDefaults(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, encoding="hex")


class Base58Model_WithPadding(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, encoding="b58", pad=True)


class Base62Model_WithPadding(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, encoding="b62", pad=True)


class HexModel_WithPadding(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, encoding="hex", pad=True)


class Base62Model_WithRandomize(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, randomize=True)


class HexModel_WithRandomize(models.Model):
    id = SpicyBigAutoField("ex", primary_key=True, encoding="hex", randomize=True)

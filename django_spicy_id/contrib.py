from . import fields


def monkey_patch_drf():
    """Monkey-patch Django Rest Framework to be aware of our field types.

    Instructs DRF to treat our fields like CharFields.
    """
    from rest_framework.fields import CharField
    from rest_framework.serializers import ModelSerializer

    for f in (fields.SpicyAutoField, fields.SpicyBigAutoField, fields.SpicySmallAutoField):
        ModelSerializer.serializer_field_mapping[f] = CharField

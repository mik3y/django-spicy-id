class SpicyUrlConverter:
    """A reusable Django 'custom path converter' class for spicy IDs.

    This class should not be used directly. Rather, use the `.url_converter`
    instance that is available on every spicy field.

    Reference: https://docs.djangoproject.com/en/3.2/topics/http/urls/#registering-custom-path-converters
    """

    def __new__(cls, regex, *args, **kwargs):
        instance = super(SpicyUrlConverter, cls).__new__(cls, *args, **kwargs)
        instance.regex = regex
        return instance

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


def get_url_converter(model, field_name):
    """Returns a Django path-converter class for `field_name` on `model`.

    Register the result with `django.urls.register_converter` so that only valid
    ids for that field match in your URL patterns. See "Registering URLs" in the
    README for example usage.
    """
    field = model._meta.get_field(field_name)
    return lambda: SpicyUrlConverter(field.re_pattern)

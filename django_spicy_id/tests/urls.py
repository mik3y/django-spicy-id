from django.urls import path, register_converter

from django_spicy_id import get_url_converter

from . import models, views

register_converter(get_url_converter(models.HexModel_WithDefaults, "id"), "spicy_hex_id")
register_converter(get_url_converter(models.Base58Model_WithPadding, "id"), "spicy_b58_id")

urlpatterns = [
    path("example/hex-nopad/<spicy_hex_id:id>", views.receive_id_and_serve_200),
    path("example/b58-pad/<spicy_b58_id:id>", views.receive_id_and_serve_200),
]

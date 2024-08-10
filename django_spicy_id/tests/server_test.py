from django.test import Client, TestCase


class ServerTestCase(TestCase):
    def test_valid_spicy_urls_hex(self):
        c = Client()

        # Valid IDs.
        for id in ("ex_1", "ex_1234", "ex_deadbeef"):
            response = c.get(f"/example/hex-nopad/{id}")
            self.assertEqual(200, response.status_code, f"expected 200 for {id}")

        # Invalid ids (including padded "valid" ids, which this field
        # is not configured to accept).
        for bad_id in ("bloop", "ex_gf", "ex_0001"):
            response = c.get(f"/example/hex-nopad/{bad_id}")
            self.assertEqual(404, response.status_code, f"expected 404 for {bad_id}")

    def test_valid_spicy_urls_b58(self):
        c = Client()

        # Valid IDs.
        for id in ("ex_1111111aj12", "ex_11111111111", "ex_111111BukQL"):
            response = c.get(f"/example/b58-pad/{id}")
            self.assertEqual(200, response.status_code, f"expected 200 for {id}")

        # Invalid ids (including padded "valid" ids, which this field
        # is not configured to accept).
        for bad_id in ("bloop", "ex_1", "ex_!@()*"):
            response = c.get(f"/example/b58-pad/{bad_id}")
            self.assertEqual(404, response.status_code, f"expected 404 for {bad_id}")

import asyncio
import unittest
from unittest.mock import patch

from backend.url_safety import get_public_redirect_safe, validate_public_http_url


class URLSafetyTest(unittest.TestCase):
    def test_rejects_loopback_and_private_addresses(self):
        for url in ("http://127.0.0.1", "http://10.0.0.1", "http://[::1]"):
            with self.assertRaises(ValueError):
                validate_public_http_url(url)

    def test_rejects_non_http_urls_and_credentials(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com"):
            with self.assertRaises(ValueError):
                validate_public_http_url(url)

    def test_blocks_redirect_to_loopback_before_second_request(self):
        class Redirect:
            is_redirect = True
            headers = {"location": "http://127.0.0.1/admin"}
            url = "https://public.example/image"

        class Client:
            calls = 0

            async def get(self, *_args, **_kwargs):
                self.calls += 1
                return Redirect()

        client = Client()
        def resolve(host, *_args):
            address = "127.0.0.1" if host == "127.0.0.1" else "8.8.8.8"
            return [(None, None, None, None, (address, 0))]

        with patch("backend.url_safety.socket.getaddrinfo", side_effect=resolve):
            with self.assertRaises(ValueError):
                asyncio.run(get_public_redirect_safe(client, "https://public.example/image"))
        self.assertEqual(client.calls, 1)


if __name__ == "__main__":
    unittest.main()

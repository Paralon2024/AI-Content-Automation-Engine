import io
import json
import socket
import unittest
from unittest.mock import patch

from tools.common.gemini_http import post_interaction


class GeminiHttpTests(unittest.TestCase):
    def _call(self):
        return post_interaction(
            api_url="https://example.invalid/interactions",
            api_key="test-key",
            payload={"model": "test-model"},
            timeout_seconds=7,
            operation="video generation",
        )

    @patch("tools.common.gemini_http.urllib.request.urlopen")
    def test_returns_json_object(self, urlopen):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"status":"completed"}'
        urlopen.return_value = response

        self.assertEqual(self._call(), {"status": "completed"})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 7)

    @patch("tools.common.gemini_http.urllib.request.urlopen")
    def test_http_error_includes_provider_message(self, urlopen):
        error = urllib_error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            "https://example.invalid/interactions",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":{"message":"quota exceeded"}}'),
        )
        urlopen.side_effect = error

        with self.assertRaisesRegex(RuntimeError, "HTTP 429.*quota exceeded"):
            self._call()

    @patch("tools.common.gemini_http.urllib.request.urlopen")
    def test_timeout_warns_that_generation_outcome_is_unknown(self, urlopen):
        urlopen.side_effect = socket.timeout("read timed out")

        with self.assertRaisesRegex(RuntimeError, "outcome is unknown"):
            self._call()

    @patch("tools.common.gemini_http.urllib.request.urlopen")
    def test_rejects_non_object_json(self, urlopen):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'[]'
        urlopen.return_value = response

        with self.assertRaisesRegex(RuntimeError, "unexpected JSON response type"):
            self._call()


if __name__ == "__main__":
    unittest.main()

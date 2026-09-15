from __future__ import annotations

import io
import struct
import unittest

from local_agent.platform import chrome_native_host


class ChromeNativeHostTests(unittest.TestCase):
    def test_message_round_trip_uses_native_messaging_frame(self) -> None:
        stream = io.BytesIO()
        message = {"type": "ack", "protocol_version": 1, "event_id": "evt-" + "a" * 32}
        chrome_native_host.write_message(stream, message)
        encoded = stream.getvalue()
        declared = struct.unpack("=I", encoded[:4])[0]
        self.assertEqual(declared, len(encoded) - 4)
        stream.seek(0)
        self.assertEqual(chrome_native_host.read_message(stream), message)

    def test_inbound_message_size_is_bounded(self) -> None:
        stream = io.BytesIO(struct.pack("=I", chrome_native_host.MAX_INBOUND_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "invalid native message length"):
            chrome_native_host.read_message(stream)

    def test_caller_origin_must_be_exact_chrome_extension_origin(self) -> None:
        extension_id = "a" * 32
        self.assertEqual(
            chrome_native_host._validate_origin(["host", f"chrome-extension://{extension_id}/"]),
            f"chrome-extension://{extension_id}/",
        )
        for origin in (
            "",
            f"chrome-extension://{extension_id}",
            "https://chatgpt.com/",
            "chrome-extension://wildcard/",
        ):
            with self.subTest(origin=origin):
                with self.assertRaisesRegex(ValueError, "caller origin"):
                    chrome_native_host._validate_origin(["host", origin])

    def test_host_hello_is_minimal_and_versioned(self) -> None:
        hello = chrome_native_host._hello()
        self.assertEqual(hello["type"], "hello")
        self.assertEqual(hello["protocol_version"], chrome_native_host.PROTOCOL_VERSION)
        self.assertEqual(hello["host_name"], chrome_native_host.HOST_NAME)
        self.assertNotIn("path", hello)
        self.assertNotIn("command", hello)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import socket
import struct
import threading
import unittest
from unittest import mock

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

    def test_unknown_message_type_fails_closed(self) -> None:
        server, client = socket.socketpair()
        self.addCleanup(server.close)
        self.addCleanup(client.close)
        client.settimeout(3.0)
        server_stream = server.makefile("rwb", buffering=0)
        client_stream = client.makefile("rwb", buffering=0)
        self.addCleanup(server_stream.close)
        self.addCleanup(client_stream.close)
        outcome: list[int] = []
        origin = "chrome-extension://" + "a" * 32 + "/"
        thread = threading.Thread(
            target=lambda: outcome.append(
                chrome_native_host.run_host(
                    stdin=server_stream,
                    stdout=server_stream,
                    argv=["host", origin],
                )
            ),
            daemon=True,
        )
        thread.start()
        self.assertEqual(chrome_native_host.read_message(client_stream), chrome_native_host._hello())
        chrome_native_host.write_message(
            client_stream,
            {"type": "execute", "protocol_version": chrome_native_host.PROTOCOL_VERSION},
        )
        error = chrome_native_host.read_message(client_stream)
        self.assertEqual(error["type"], "error")
        self.assertEqual(error["reason"], "unknown_message_type")
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [2])

    def test_ack_before_handshake_and_invalid_ack_fail_closed(self) -> None:
        for message, expected in (
            (
                {
                    "type": "ack",
                    "protocol_version": chrome_native_host.PROTOCOL_VERSION,
                    "event_id": "evt-" + "a" * 32,
                },
                "handshake_required",
            ),
        ):
            with self.subTest(expected=expected):
                server, client = socket.socketpair()
                server_stream = server.makefile("rwb", buffering=0)
                client_stream = client.makefile("rwb", buffering=0)
                client.settimeout(3.0)
                outcome: list[int] = []
                origin = "chrome-extension://" + "a" * 32 + "/"
                thread = threading.Thread(
                    target=lambda: outcome.append(
                        chrome_native_host.run_host(
                            stdin=server_stream,
                            stdout=server_stream,
                            argv=["host", origin],
                        )
                    ),
                    daemon=True,
                )
                thread.start()
                self.assertEqual(chrome_native_host.read_message(client_stream), chrome_native_host._hello())
                chrome_native_host.write_message(client_stream, message)
                error = chrome_native_host.read_message(client_stream)
                self.assertEqual(error["reason"], expected)
                thread.join(timeout=2.0)
                self.assertEqual(outcome, [2])
                client_stream.close()
                server_stream.close()
                client.close()
                server.close()

        server, client = socket.socketpair()
        server_stream = server.makefile("rwb", buffering=0)
        client_stream = client.makefile("rwb", buffering=0)
        client.settimeout(3.0)
        outcome = []
        origin = "chrome-extension://" + "a" * 32 + "/"
        thread = threading.Thread(
            target=lambda: outcome.append(
                chrome_native_host.run_host(
                    stdin=server_stream,
                    stdout=server_stream,
                    argv=["host", origin],
                )
            ),
            daemon=True,
        )
        thread.start()
        self.assertEqual(chrome_native_host.read_message(client_stream), chrome_native_host._hello())
        chrome_native_host.write_message(
            client_stream,
            {"type": "hello", "protocol_version": chrome_native_host.PROTOCOL_VERSION},
        )
        self.assertEqual(chrome_native_host.read_message(client_stream), chrome_native_host._hello())
        chrome_native_host.write_message(
            client_stream,
            {"type": "ack", "protocol_version": chrome_native_host.PROTOCOL_VERSION, "event_id": "bad"},
        )
        error = chrome_native_host.read_message(client_stream)
        self.assertEqual(error["reason"], "invalid_ack")
        thread.join(timeout=2.0)
        self.assertEqual(outcome, [2])
        client_stream.close()
        server_stream.close()
        client.close()
        server.close()

    def test_connected_host_delivers_event_created_after_handshake_and_acks_it(self) -> None:
        event_id = "evt-" + "b" * 32
        event = {
            "schema_version": 1,
            "event_id": event_id,
            "event_type": "task_result_ready",
            "emitted_at": "2026-09-15T22:00:00+00:00",
            "repository_id": "matrixhub",
            "repository": "MichalMatu/MatrixHub",
            "agent_binding": "033327ab-700d-43b4-9b3b-caff1acaa2c7",
            "task_id": "host-live-event-1",
            "result_status": "done",
        }
        pending: list[dict[str, object]] = []
        acknowledged: list[str] = []
        server, client = socket.socketpair()
        self.addCleanup(server.close)
        self.addCleanup(client.close)
        client.settimeout(3.0)
        server_stream = server.makefile("rwb", buffering=0)
        client_stream = client.makefile("rwb", buffering=0)
        self.addCleanup(server_stream.close)
        self.addCleanup(client_stream.close)

        def pending_events() -> list[dict[str, object]]:
            return [dict(item) for item in pending]

        def acknowledge(received_event_id: str) -> bool:
            acknowledged.append(received_event_id)
            pending[:] = [item for item in pending if item.get("event_id") != received_event_id]
            return True

        outcome: list[int] = []
        origin = "chrome-extension://" + "a" * 32 + "/"
        with (
            mock.patch.object(chrome_native_host.result_events, "pending_events", side_effect=pending_events),
            mock.patch.object(chrome_native_host.result_events, "acknowledge_event", side_effect=acknowledge),
            mock.patch.object(chrome_native_host, "POLL_SECONDS", 0.01),
            mock.patch.object(chrome_native_host, "RESEND_SECONDS", 0.05),
        ):
            thread = threading.Thread(
                target=lambda: outcome.append(
                    chrome_native_host.run_host(
                        stdin=server_stream,
                        stdout=server_stream,
                        argv=["host", origin],
                    )
                ),
                daemon=True,
            )
            thread.start()

            initial_hello = chrome_native_host.read_message(client_stream)
            self.assertEqual(initial_hello, chrome_native_host._hello())
            chrome_native_host.write_message(
                client_stream,
                {"type": "hello", "protocol_version": chrome_native_host.PROTOCOL_VERSION},
            )
            negotiated_hello = chrome_native_host.read_message(client_stream)
            self.assertEqual(negotiated_hello, chrome_native_host._hello())

            pending.append(event)
            delivered = chrome_native_host.read_message(client_stream)
            self.assertEqual(delivered["type"], "event")
            self.assertEqual(delivered["event"]["event_id"], event_id)
            chrome_native_host.write_message(
                client_stream,
                {
                    "type": "ack",
                    "protocol_version": chrome_native_host.PROTOCOL_VERSION,
                    "event_id": event_id,
                },
            )

            for _ in range(100):
                if acknowledged:
                    break
                threading.Event().wait(0.01)
            self.assertEqual(acknowledged, [event_id])
            self.assertEqual(pending, [])

            client.shutdown(socket.SHUT_WR)
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive(), "native host must terminate after browser EOF")
            self.assertEqual(outcome, [0])


if __name__ == "__main__":
    unittest.main()

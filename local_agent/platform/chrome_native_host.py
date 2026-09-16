"""Read-only Chrome Native Messaging transport for Local Agent result events."""

from __future__ import annotations

import json
import re
import selectors
import struct
import sys
import time
from typing import Any, BinaryIO

from local_agent.foundation import result_events
from local_agent.version import RELEASE_VERSION

HOST_NAME = "com.michalmatu.local_agent_bridge"
PROTOCOL_VERSION = 1
MAX_INBOUND_BYTES = 64 * 1024
RESEND_SECONDS = 5.0
POLL_SECONDS = 0.5
_EXTENSION_ORIGIN_RE = re.compile(r"^chrome-extension://[a-p]{32}/$")
_EVENT_ID_RE = re.compile(r"^evt-[0-9a-f]{32}$")


def _read_exact(stream: BinaryIO, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    header = _read_exact(stream, 4)
    if header is None:
        return None
    length = struct.unpack("=I", header)[0]
    if length < 2 or length > MAX_INBOUND_BYTES:
        raise ValueError(f"invalid native message length: {length}")
    payload = _read_exact(stream, length)
    if payload is None:
        raise EOFError("native message ended before declared payload length")
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("native message root must be an object")
    return message


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(payload) > result_events.MAX_EVENT_BYTES * 2:
        raise ValueError("native message exceeds Local Agent transport bound")
    stream.write(struct.pack("=I", len(payload)))
    stream.write(payload)
    stream.flush()


def _hello() -> dict[str, Any]:
    return {
        "type": "hello",
        "protocol_version": PROTOCOL_VERSION,
        "host_name": HOST_NAME,
        "host_version": RELEASE_VERSION,
    }


def _error(reason: str) -> dict[str, Any]:
    return {
        "type": "error",
        "protocol_version": PROTOCOL_VERSION,
        "reason": reason,
    }


def _validate_origin(argv: list[str]) -> str:
    if len(argv) < 2 or not _EXTENSION_ORIGIN_RE.fullmatch(argv[1]):
        raise ValueError("native host caller origin is missing or invalid")
    return argv[1]


def run_host(
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    argv: list[str] | None = None,
) -> int:
    input_stream = stdin or sys.stdin.buffer
    output_stream = stdout or sys.stdout.buffer
    arguments = list(sys.argv if argv is None else argv)
    _validate_origin(arguments)

    selector = selectors.DefaultSelector()
    selector.register(input_stream, selectors.EVENT_READ)
    ready = False
    last_sent: dict[str, float] = {}
    write_message(output_stream, _hello())

    while True:
        readable = selector.select(timeout=POLL_SECONDS)
        if readable:
            message = read_message(input_stream)
            if message is None:
                return 0
            message_type = message.get("type")
            protocol_version = message.get("protocol_version")
            if message_type == "hello":
                if ready:
                    write_message(output_stream, _error("duplicate_hello"))
                    return 2
                if protocol_version != PROTOCOL_VERSION:
                    write_message(output_stream, _error("protocol_mismatch"))
                    return 2
                ready = True
                write_message(output_stream, _hello())
            elif message_type == "ack":
                if not ready:
                    write_message(output_stream, _error("handshake_required"))
                    return 2
                if protocol_version != PROTOCOL_VERSION:
                    write_message(output_stream, _error("protocol_mismatch"))
                    return 2
                event_id = message.get("event_id")
                if not isinstance(event_id, str) or not _EVENT_ID_RE.fullmatch(event_id):
                    write_message(output_stream, _error("invalid_ack"))
                    return 2
                if event_id not in last_sent:
                    write_message(output_stream, _error("ack_unknown_event"))
                    return 2
                result_events.acknowledge_event(event_id)
                last_sent.pop(event_id, None)
            else:
                write_message(output_stream, _error("unknown_message_type"))
                return 2

        if not ready:
            continue

        now = time.monotonic()
        pending = result_events.pending_events()
        pending_ids = {str(event["event_id"]) for event in pending}
        for event_id in tuple(last_sent):
            if event_id not in pending_ids:
                last_sent.pop(event_id, None)

        for event in pending:
            event_id = str(event["event_id"])
            previous = last_sent.get(event_id)
            if previous is not None and now - previous < RESEND_SECONDS:
                continue
            write_message(
                output_stream,
                {
                    "type": "event",
                    "protocol_version": PROTOCOL_VERSION,
                    "event": event,
                },
            )
            last_sent[event_id] = now


def main() -> int:
    try:
        return run_host()
    except (BrokenPipeError, EOFError):
        return 0
    except Exception as exc:
        print(f"Local Agent native host error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Executable shim for the packaged guarded Local Agent entrypoint."""

import sys

from local_agent import entrypoint as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

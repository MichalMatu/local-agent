#!/usr/bin/env python3
"""Temporary module alias for packaged local operator controls."""

import sys

from local_agent.operator import local as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

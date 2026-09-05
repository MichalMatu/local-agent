#!/usr/bin/env python3
"""Compatibility executable/module alias for packaged diagnostics CLI."""

import sys

from local_agent.cli import diagnostics as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

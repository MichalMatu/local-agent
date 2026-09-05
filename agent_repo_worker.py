#!/usr/bin/env python3
"""Compatibility executable/module alias for packaged repository worker."""

import sys

from local_agent.repository import worker as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

#!/usr/bin/env python3
"""Compatibility executable/module alias for packaged parallel worker."""

import sys

from local_agent.supervisor import worker as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
